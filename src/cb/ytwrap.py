# cb/ytwrap.py
from __future__ import annotations

import shlex
import subprocess
from itertools import islice
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .utils import print_download_summary


def run(cmd: List[str], cwd: Optional[Path] = None) -> int:
    print("▶", " ".join(shlex.quote(c) for c in cmd))
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None)


def print_lines(cmd: List[str]) -> Iterable[str]:
    p = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
    )
    for line in p.stdout:
        yield line.strip()
    p.wait()


def duration_map(urls: Iterable[str]) -> dict[str, float]:
    out: Dict[str, float] = {}
    for u in urls:
        for line in print_lines(
            ["yt-dlp", "--skip-download", "--print", "%(duration)s", u]
        ):
            try:
                out[u] = float(line)
            except Exception:
                out[u] = -1.0
    return out


def fetch(
    url: str,
    out_template: str,
    audio_fmt="mp3",
    quality="0",
    embed=True,
    add_meta=True,
    write_thumb=False,
    convert_jpg=True,
    parse_meta=True,
) -> int:
    print(f"[ytwrap] Starting SoundCloud download:")
    print(f"  URL: {url}")
    print(f"  Format: {audio_fmt} @ quality {quality}")
    print(f"  Output template: {out_template}")
    
    cmd = ["yt-dlp", "-x", "--audio-format", audio_fmt, "--audio-quality", quality]
    if embed:
        cmd += ["--embed-metadata", "--embed-thumbnail"]
    if add_meta:
        cmd += ["--add-metadata"]
    if write_thumb:
        cmd += ["--write-thumbnail"]  # default False -> no loose JPGs
    if convert_jpg:
        cmd += ["--convert-thumbnails", "jpg"]
    if parse_meta:
        # singles-style: only artist + date
        cmd += [
            "--parse-metadata",
            "%(uploader|uploader_id)s:%(artist)s",
            "--parse-metadata",
            "%(upload_date>%Y-%m-%d)s:%(date)s",
        ]
    cmd += ["-o", out_template, url]
    
    result = run(cmd)
    
    if result == 0:
        print(f"[ytwrap] ✓ SoundCloud download completed successfully")
    else:
        print(f"[ytwrap] ✗ SoundCloud download failed with exit code {result}")
    
    return result


def fetch_many(
    urls: List[str],
    out_template: str,
    audio_fmt="mp3",
    quality="0",
    embed=True,
    add_meta=True,
    write_thumb=False,
    convert_jpg=True,
    parse_meta=True,
    max_seconds: int | None = None,
    dry: bool = False,
) -> int:
    original_count = len(urls)
    
    # Filter by duration if specified
    if max_seconds is not None:
        print(f"[ytwrap] Filtering tracks by duration (<{max_seconds}s)...")
        dmap = duration_map(urls)
        urls = [u for u in urls if 0 < dmap.get(u, 0) < max_seconds]
        filtered_count = len(urls)
        if filtered_count < original_count:
            print(f"[ytwrap] Filtered: {filtered_count}/{original_count} tracks within duration limit")
    
    if not urls:
        print("[ytwrap] No tracks to download after filtering")
        return 0
        
    if dry:
        print(f"[DRY] Would download {len(urls)} SoundCloud tracks:")
        for i, u in enumerate(urls, 1):
            print(f"  [{i}/{len(urls)}] {u}")
        return 0
    
    print(f"[ytwrap] Starting SoundCloud download of {len(urls)} tracks")
    print(f"[ytwrap] Configuration: {audio_fmt} @ quality {quality}")
    
    rc = 0
    success_count = 0
    failed_urls = []
    
    for i, u in enumerate(urls, 1):
        print(f"\n[ytwrap] Progress: [{i}/{len(urls)}] Downloading...")
        
        result = fetch(
            u,
            out_template,
            audio_fmt,
            quality,
            embed,
            add_meta,
            write_thumb,
            convert_jpg,
            parse_meta,
        )
        
        if result == 0:
            success_count += 1
        else:
            failed_urls.append(u)
        
        rc = result or rc
    
    # Comprehensive final summary
    print_download_summary(
        platform="SoundCloud",
        successful=success_count,
        total=len(urls),
        failed_items=failed_urls,
        destination=Path(out_template).parent,
        format_info=f"{audio_fmt} @ quality {quality}",
        additional_info={
            "Metadata embedding": "enabled" if embed else "disabled",
            "Thumbnails": "enabled" if write_thumb else "disabled",
            "Metadata parsing": "enabled" if parse_meta else "disabled",
            "Original tracks requested": str(original_count) if original_count != len(urls) else None
        }
    )
    
    return rc


# ---- Search & cluster helpers ----


def sc_search_urls(
    query: str, kind: str = "tracks", max_results: int = 20
) -> List[str]:
    """
    Use yt-dlp's SoundCloud search extractor: scsearchN:QUERY plus optional type.
    kind: 'tracks' (default), 'sets', 'users'
    """
    qualifier = ""
    if kind == "sets":
        qualifier = " type:playlists"
    elif kind == "users":
        qualifier = " type:users"
    n = max(1, int(max_results or 20))
    q = f"scsearch{n}:{query}{qualifier}"
    return list(
        islice(print_lines(["yt-dlp", "--flat-playlist", "--print", "%(url)s", q]), n)
    )


def sc_search_url_title_pairs(
    query: str, kind: str = "tracks", max_results: int = 20
) -> List[tuple[str, str]]:
    # also get uploader to use for clustering
    qualifier = ""
    if kind == "sets":
        qualifier = " type:playlists"
    elif kind == "users":
        qualifier = " type:users"
    n = max(1, int(max_results or 20))
    q = f"scsearch{n}:{query}{qualifier}"
    pairs: List[tuple[str, str]] = []
    for line in print_lines(
        ["yt-dlp", "--flat-playlist", "--print", "%(url)s\t%(uploader_id|uploader)s", q]
    ):
        if "\t" in line:
            url, uploader = line.split("\t", 1)
            pairs.append((url, uploader))
    return pairs


def list_flat(url: str) -> List[str]:
    """Return child item URLs for any SoundCloud collection page (user sections, playlists)."""
    return list(print_lines(["yt-dlp", "--flat-playlist", "--print", "%(url)s", url]))


def normalize_user_root(user_or_url: str) -> str:
    """
    Accepts a profile URL or a bare handle and returns:
      https://soundcloud.com/<handle>
    """
    u = user_or_url.strip()
    if u.startswith("http"):
        return "https://soundcloud.com/" + u.split("soundcloud.com/")[-1].strip("/")
    return f"https://soundcloud.com/{u.strip('/')}"
