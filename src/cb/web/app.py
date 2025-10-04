"""Web UI for CloudBuccaneer using FastAPI."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .. import spotwrap, ytwrap
from ..bpm import BPMDetector, find_audio_files, format_bpm_result
from ..renamer import apply_changes, plan_renames
from ..utils import load_config


app = FastAPI(title="CloudBuccaneer Web UI", version="0.1.0")

# Get the directory of this file
web_dir = Path(__file__).parent
static_dir = web_dir / "static"
templates_dir = web_dir / "templates"

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(templates_dir))


# Models for API requests
class FetchRequest(BaseModel):
    url: str
    dest: Optional[str] = None
    max_seconds: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    kind: str = "tracks"
    max_results: int = 20


class RenameRequest(BaseModel):
    folder: str


class CleanRequest(BaseModel):
    folder: str
    images: bool = True
    parts: bool = True
    webp: bool = True


class BPMRequest(BaseModel):
    target: str
    parallel: bool = False
    advanced: bool = True


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main web UI page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    try:
        config = load_config()
        return JSONResponse(content=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/fetch")
async def fetch_url(req: FetchRequest):
    """Download from SoundCloud or Spotify URL."""
    try:
        cfg = load_config()
        base = Path(req.dest or cfg["download_dir"]).expanduser()
        base.mkdir(parents=True, exist_ok=True)

        # Check if Spotify URL
        if spotwrap.validate_spotify_url(req.url):
            url = spotwrap.normalize_spotify_url(req.url)
            spotify_dest = cfg.get("spotify", {}).get("download_dir", str(base))
            spotify_base = Path(req.dest or spotify_dest).expanduser()
            spotify_base.mkdir(parents=True, exist_ok=True)
            
            out_template = str(spotify_base / "{artist} - {title}.{output-ext}")
            result = spotwrap.fetch(url, out_template)
            
            return {
                "success": result == 0,
                "platform": "Spotify",
                "destination": str(spotify_base)
            }
        else:
            # SoundCloud download
            out_tmpl = str(base / cfg.get("out_template", "%(title)s - %(artist|uploader)s.%(ext)s"))
            result = ytwrap.fetch(req.url, out_tmpl, max_seconds=req.max_seconds)
            
            return {
                "success": result == 0,
                "platform": "SoundCloud",
                "destination": str(base)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def search(req: SearchRequest):
    """Search SoundCloud or Spotify."""
    try:
        results = ytwrap.sc_search_url_title_pairs(req.query, req.kind, req.max_results)
        return {
            "success": True,
            "results": [{"url": url, "title": title} for url, title in results]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rename")
async def rename_files(req: RenameRequest):
    """Rename files in a folder."""
    try:
        folder = Path(req.folder).expanduser()
        if not folder.is_dir():
            raise HTTPException(status_code=400, detail="Not a valid directory")
        
        cfg = load_config()
        rename_cfg = cfg.get("rename", {})
        
        changes = plan_renames(
            folder,
            ascii=rename_cfg.get("ascii", True),
            keep_track=rename_cfg.get("keep_track", True),
            move_covers=rename_cfg.get("move_covers", True)
        )
        
        if not changes:
            return {"success": True, "message": "No changes needed", "count": 0}
        
        apply_changes(changes)
        
        return {
            "success": True,
            "message": f"Renamed {len(changes)} file(s)",
            "count": len(changes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clean")
async def clean_folder(req: CleanRequest):
    """Clean leftover files from a folder."""
    try:
        folder = Path(req.folder).expanduser()
        if not folder.is_dir():
            raise HTTPException(status_code=400, detail="Not a valid directory")
        
        patterns = []
        if req.images:
            patterns += ["*.jpg", "*.jpeg", "*.png"]
        if req.webp:
            patterns += ["*.webp"]
        if req.parts:
            patterns += ["*.part", "*.temp"]
        
        removed = 0
        for pat in patterns:
            for p in folder.rglob(pat):
                try:
                    p.unlink()
                    removed += 1
                except Exception:
                    pass
        
        return {
            "success": True,
            "message": f"Removed {removed} file(s)",
            "count": removed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bpm")
async def detect_bpm(req: BPMRequest):
    """Detect BPM of audio files."""
    try:
        target = Path(req.target).expanduser()
        if not target.exists():
            raise HTTPException(status_code=400, detail="Path does not exist")
        
        detector = BPMDetector(use_advanced=req.advanced)
        results = []
        
        if target.is_file():
            if not detector.is_supported_format(target):
                raise HTTPException(status_code=400, detail="Unsupported file format")
            
            bpm = detector.detect_bpm(target)
            results.append({
                "file": str(target.name),
                "bpm": bpm,
                "formatted": format_bpm_result(target, bpm)
            })
        else:
            # Directory - find all audio files
            audio_files = find_audio_files(target, recursive=True)
            for audio_file in audio_files:
                try:
                    bpm = detector.detect_bpm(audio_file)
                    results.append({
                        "file": str(audio_file.relative_to(target)),
                        "bpm": bpm,
                        "formatted": format_bpm_result(audio_file, bpm)
                    })
                except Exception:
                    results.append({
                        "file": str(audio_file.relative_to(target)),
                        "bpm": None,
                        "formatted": f"Error analyzing {audio_file.name}"
                    })
        
        return {
            "success": True,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_server(host: str = "127.0.0.1", port: int = 8080):
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
