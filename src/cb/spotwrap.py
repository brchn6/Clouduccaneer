# cb/spotwrap.py
from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlsplit, urlunsplit


# ---------------------------
# helpers: shell + streaming
# ---------------------------

def run(cmd: List[str], cwd: Optional[Path] = None, quiet_stderr: bool = False) -> int:
    """
    Execute a subprocess command and return its exit code.
    """
    print("▶", " ".join(shlex.quote(c) for c in cmd))
    return subprocess.call(
        cmd,
        cwd=str(cwd) if cwd else None,
        stderr=(subprocess.DEVNULL if quiet_stderr else None),
    )


def print_lines(cmd: List[str]) -> Iterable[str]:
    """
    Stream stdout lines from a subprocess command.
    """
    p = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
    )
    assert p.stdout is not None
    for line in p.stdout:
        yield line.strip()
    p.wait()


# ---------------------------
# Spotify URL utilities
# ---------------------------

def validate_spotify_url(url: str) -> bool:
    """
    Quick check for spotify URLs/URIs.
    """
    return "open.spotify.com" in url or url.startswith("spotify:")


def normalize_spotify_url(url: str) -> str:
    """
    Normalize Spotify URLs to a clean https form with no query/fragment.
    Converts spotify: URIs to https URLs, then strips ?query and #fragment.
    """
    if url.startswith("spotify:"):
        parts = url.split(":")
        if len(parts) >= 3:
            # spotify:<type>:<id>[?si=...]  -> https://open.spotify.com/<type>/<id>
            _type, _id = parts[1], parts[2]
            return f"https://open.spotify.com/{_type}/{_id}"

    try:
        u = urlsplit(url)
        if "open.spotify.com" in u.netloc:
            # drop query + fragment (e.g. ?si=..., ?pi=..., #...)
            return urlunsplit((u.scheme, u.netloc, u.path, "", ""))
    except Exception:
        pass

    return url


# ---------------------------
# OAuth convenience
# ---------------------------

def _warn_if_missing_oauth_vars() -> None:
    """
    SpotDL needs Spotipy OAuth env vars for --user-auth.
    This warns if they’re missing (does not hard-fail).
    """
    missing = [
        v for v in ("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI")
        if not os.environ.get(v)
    ]
    if missing:
        print(
            "[spotwrap] NOTE: missing env vars for Spotify OAuth ->",
            ", ".join(missing),
            "\n          You will be asked to log in anyway; set them to skip prompts.\n"
            "          Example:\n"
            "            export SPOTIPY_CLIENT_ID=...\n"
            "            export SPOTIPY_CLIENT_SECRET=... \n"
            "            export SPOTIPY_REDIRECT_URI=http://localhost:8888/callback\n"
        )


# ---------------------------
# SpotDL command builders
# ---------------------------

def _spotdl_cmd_base(user_auth: bool) -> List[str]:
    """
    Base SpotDL command, optionally enabling user authentication.
    """
    cmd = ["spotdl"]
    if user_auth:
        _warn_if_missing_oauth_vars()
        cmd += ["--user-auth"]
    return cmd


# ---------------------------
# Primary API
# ---------------------------

def fetch(
    url: str,
    out_template: str,
    audio_fmt: str = "mp3",
    quality: str = "320k",
    lyrics: bool = False,
    playlist_numbering: bool = True,
    embed_metadata: bool = True,         # kept for API compat; SpotDL embeds by default
    quiet_stderr: bool = True,
    user_auth: bool = False,
) -> int:
    """
    Download a Spotify track/playlist/album using SpotDL.

    - Cleans the URL (removes query/fragment)
    - Adds --user-auth if requested (needed for private/collab playlists)
    """
    if not validate_spotify_url(url):
        print(f"[spotwrap] Not a Spotify URL: {url}")
        return 2

    url = normalize_spotify_url(url)

    cmd = _spotdl_cmd_base(user_auth) + ["download", url]
    cmd += ["--format", audio_fmt]
    cmd += ["--bitrate", quality]
    cmd += ["--output", out_template]

    if lyrics:
        cmd += ["--lyrics", "genius", "musixmatch"]
    if playlist_numbering:
        cmd += ["--playlist-numbering"]

    # embed_metadata: SpotDL v4 embeds by default; kept as a placeholder flag

    return run(cmd, quiet_stderr=quiet_stderr)


def fetch_many(
    urls: List[str],
    out_dir: str,
    audio_fmt: str = "mp3",
    quality: str = "320k",
    lyrics: bool = False,
    playlist_numbering: bool = True,
    embed_metadata: bool = True,         # placeholder
    dry: bool = False,
    throttle_seconds: float = 1.5,
    user_auth: bool = False,
) -> int:
    """
    Download multiple Spotify URLs with gentle throttling.
    """
    if dry:
        for u in urls:
            print(f"[DRY] would fetch spotify: {normalize_spotify_url(u)}")
        return 0

    rc = 0
    for i, u in enumerate(urls):
        rc = (
            fetch(
                u,
                str(Path(out_dir) / "{artist} - {title}.{ext}"),
                audio_fmt=audio_fmt,
                quality=quality,
                lyrics=lyrics,
                playlist_numbering=playlist_numbering,
                embed_metadata=embed_metadata,
                user_auth=user_auth,
            )
            or rc
        )
        if i < len(urls) - 1 and throttle_seconds > 0:
            time.sleep(throttle_seconds)
    return rc


# ---------------------------
# Metadata / search helpers
# ---------------------------

def get_metadata(url: str) -> Dict[str, str]:
    """
    Get metadata for a Spotify URL without downloading.

    Uses `spotdl meta <url>` and parses its stdout (best-effort).
    """
    url = normalize_spotify_url(url)
    try:
        cmd = _spotdl_cmd_base(user_auth=False) + ["meta", url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().splitlines()
        metadata: Dict[str, str] = {}
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()
        return metadata
    except subprocess.CalledProcessError:
        return {}


def search_spotify(query: str, limit: int = 20) -> List[str]:
    """
    Approximate search using SpotDL's search pipeline.
    Returns a list of Spotify URLs if they appear in stdout.
    """
    cmd = _spotdl_cmd_base(user_auth=False) + ["download", "--search-query", query, "--save-file", "-"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        urls: List[str] = []
        for line in result.stdout.splitlines():
            if "open.spotify.com" in line:
                urls.extend(re.findall(r"https://open\.spotify\.com/[^\s)]+", line))
        # clean them
        urls = [normalize_spotify_url(u) for u in urls]
        return urls[:limit]
    except Exception:
        return []


def get_playlist_tracks(playlist_url: str) -> List[str]:
    """
    Placeholder: SpotDL handles playlists directly.
    If you ever want to expand: use spotipy to enumerate and return track URLs.
    """
    return [normalize_spotify_url(playlist_url)]
