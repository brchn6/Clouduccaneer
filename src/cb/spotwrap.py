# cb/spotwrap.py
from __future__ import annotations
import subprocess, shlex
from pathlib import Path
from typing import Iterable, Optional, List, Dict
import json

def run(cmd: List[str], cwd: Optional[Path]=None) -> int:
    print("▶", " ".join(shlex.quote(c) for c in cmd))
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None)

def print_lines(cmd: List[str]) -> Iterable[str]:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    for line in p.stdout: 
        yield line.strip()
    p.wait()

def fetch(url: str, out_dir: str, audio_fmt="mp3", quality="320k",
          lyrics=True, playlist_numbering=True, embed_metadata=True) -> int:
    """Download a Spotify track/playlist/album using spotdl."""
    cmd = ["spotdl", "download", url]
    cmd += ["--format", audio_fmt]
    cmd += ["--bitrate", quality]
    cmd += ["--output", out_dir]
    
    if lyrics:
        cmd += ["--lyrics", "genius", "musixmatch"]
    if playlist_numbering:
        cmd += ["--playlist-numbering"]
    
    return run(cmd)

def fetch_many(urls: List[str], out_dir: str, audio_fmt="mp3", quality="320k",
               lyrics=True, playlist_numbering=True, embed_metadata=True, 
               dry: bool = False) -> int:
    """Download multiple Spotify URLs."""
    if dry:
        for u in urls: 
            print(f"[DRY] would fetch spotify: {u}")
        return 0
    
    rc = 0
    for u in urls:
        rc = fetch(u, out_dir, audio_fmt, quality, lyrics, playlist_numbering, embed_metadata) or rc
    return rc

def get_metadata(url: str) -> Dict[str, str]:
    """Get metadata for a Spotify URL without downloading."""
    try:
        cmd = ["spotdl", "meta", url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Parse spotdl output to extract metadata
        # spotdl doesn't have a json output mode, so we need to parse text output
        lines = result.stdout.strip().split('\n')
        metadata = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()
        return metadata
    except subprocess.CalledProcessError:
        return {}

def search_spotify(query: str, type_filter="track", limit=20) -> List[str]:
    """Search Spotify and return URLs."""
    # Note: spotdl doesn't have a direct search command that returns URLs
    # This is a limitation we'll need to work around or use spotipy directly
    cmd = ["spotdl", "download", "--search-query", query, "--save-file", "-"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        # Parse the output to extract URLs (this is approximate)
        urls = []
        for line in result.stdout.split('\n'):
            if 'spotify.com' in line:
                # Extract Spotify URLs from the output
                import re
                matches = re.findall(r'https://open\.spotify\.com/[^\s]+', line)
                urls.extend(matches)
        return urls[:limit]
    except:
        return []

def validate_spotify_url(url: str) -> bool:
    """Check if a URL is a valid Spotify URL."""
    return 'spotify.com' in url or 'spotify:' in url

def normalize_spotify_url(url: str) -> str:
    """Normalize Spotify URL format."""
    if url.startswith('spotify:'):
        # Convert spotify: URI to https URL
        parts = url.split(':')
        if len(parts) >= 3:
            return f"https://open.spotify.com/{parts[1]}/{parts[2]}"
    return url

def get_playlist_tracks(playlist_url: str) -> List[str]:
    """Get individual track URLs from a Spotify playlist."""
    # This would require implementing playlist parsing
    # For now, return the playlist URL itself as spotdl handles playlists
    return [playlist_url]