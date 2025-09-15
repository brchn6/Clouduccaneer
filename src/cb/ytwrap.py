# cb/ytwrap.py
from __future__ import annotations
import subprocess
import shlex
from pathlib import Path
from itertools import islice
from typing import Iterable, Optional, List, Dict


def run(cmd: List[str], cwd: Optional[Path] = None) -> int:
    print("▶", " ".join(shlex.quote(c) for c in cmd))
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None)


def print_lines(cmd: List[str]) -> Iterable[str]:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    for line in p.stdout:
        yield line.strip()
    p.wait()


def duration_map(urls: Iterable[str]) -> dict[str, float]:
    out: Dict[str, float] = {}
    for u in urls:
        for line in print_lines(["yt-dlp", "--skip-download", "--print", "%(duration)s", u]):
            try:
                out[u] = float(line)
            except Exception:
                out[u] = -1.0
    return out


def fetch(url: str, out_template: str, audio_fmt="mp3", quality="0",
          embed=True, add_meta=True, write_thumb=False, convert_jpg=True,
          parse_meta=True) -> int:
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
            "--parse-metadata", "%(uploader|uploader_id)s:%(artist)s",
            "--parse-metadata", "%(upload_date>%Y-%m-%d)s:%(date)s",
        ]
    cmd += ["-o", out_template, url]
    return run(cmd)


def fetch_many(urls: List[str], out_template: str, audio_fmt="mp3", quality="0",
               embed=True, add_meta=True, write_thumb=False, convert_jpg=True,
               parse_meta=True, max_seconds: int | None = None, dry: bool = False) -> int:
    if max_seconds is not None:
        dmap = duration_map(urls)
        urls = [u for u in urls if 0 < dmap.get(u, 0) < max_seconds]
    if dry:
        for u in urls:
            print("[DRY] would fetch:", u)
        return 0
    rc = 0
    for u in urls:
        rc = fetch(u, out_template, audio_fmt, quality, embed, add_meta,
                   write_thumb, convert_jpg, parse_meta) or rc
    return rc


# ---- Search & cluster helpers ----


def sc_search_urls(query: str, kind: str = "tracks", max_results: int = 20) -> List[str]:
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
    return list(islice(print_lines(["yt-dlp", "--flat-playlist", "--print",
                                    "%(url)s", q]), n))


def sc_search_url_title_pairs(query: str, kind: str = "tracks",
                              max_results: int = 20) -> List[tuple[str, str]]:
    # also get uploader to use for clustering
    qualifier = ""
    if kind == "sets":
        qualifier = " type:playlists"
    elif kind == "users":
        qualifier = " type:users"
    n = max(1, int(max_results or 20))
    q = f"scsearch{n}:{query}{qualifier}"
    pairs: List[tuple[str, str]] = []
    for line in print_lines(["yt-dlp", "--flat-playlist", "--print",
                             "%(url)s\t%(uploader_id|uploader)s", q]):
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
