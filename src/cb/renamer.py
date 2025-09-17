# cb/renamer.py
from __future__ import annotations

"""
CloudBuccaneer renamer:
- Parse SoundCloud-style names into: [trackno] - Artist - Title
- Strip junk tokens (FREE DL, BOOTLEG, etc), labels, empty brackets
- Remove BPM markers (e.g., "160 BPM", "120bpm", "160-180 BPM")
- Normalize characters ($→s, remove !), collapse punctuation/whitespace
- Lowercase ALL-CAPS words (EVE -> eve); leave mixed-case alone
- Handle "Track NN -" prefixes found inside titles
- Collapse duplicated artist like "Artist - ARTIST - Title" -> "Artist - Title"
- Move matching cover image alongside when renaming (jpg/png/webp)
"""

import csv
import re
import shutil
from pathlib import Path
from typing import Iterable, List, Tuple

# -----------------------------
# Patterns & helpers
# -----------------------------

# remove common junk phrases (case-insensitive)
JUNK_PATTERNS = [
    r"\[?\s*free\s*dl\s*\]?",
    r"\[?\s*free\s*download\s*\]?",
    r"\(?\s*free\s*dl\s*\)?",
    r"\(?\s*bootleg\s*\)?",
    r"\(?\s*edit\s*\)?",
    r"\(?\s*remix\s*\)?",
    r"\(?\s*demo\s*\)?",
    r"\s*-\s*ridonkulous\s*records",
    r"\s*-\s*beatroot\s*records",
    r"\s*-\s*the\s*donkline",
    r"\[\s*\]",  # explicit empty brackets
]
JUNK_RE = re.compile("|".join(f"(?:{p})" for p in JUNK_PATTERNS), re.I)

# label-ish trailing chunk after last dash
LABEL_HINTS = re.compile(
    r"(records?|collective|line|wars|club|mix|edit|bootleg|remix|demo|mash\s*up)", re.I
)

# 160 BPM / 120bpm / 160-180 BPM
BPM_RE = re.compile(
    r"""
    (?:\b\d{2,3}\s*(?:-\s*\d{2,3}\s*)?bpm\b)|  # 160bpm, 160-180bpm
    (?:\b\d{2,3}\s*(?:-\s*\d{2,3}\s*)?bpm?\b) # 160 BPM (space or not)
    """,
    re.I | re.X,
)

# words that are entirely caps (2+ letters)
UPPERWORD_RE = re.compile(r"\b[A-Z]{2,}\b")

SAFE_REPLACE = [
    (r'[\\/:*?"<>|]', "_"),  # filesystem-invalid
    (r"\s+", " "),
    (r"\s+$", ""),
    (r"^\s+", ""),
]

AUDIO_EXTS = (".mp3", ".m4a", ".flac", ".ogg", ".wav")


# -----------------------------
# Normalization functions
# -----------------------------


def normalize_chars(s: str) -> str:
    # $ -> s
    s = s.replace("$", "s")
    # drop exclamation marks
    s = s.replace("!", "")
    # collapse underscores/dashes/spaces runs
    s = re.sub(r"[ _\-]{2,}", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def strip_bpm_tokens(s: str) -> str:
    s = BPM_RE.sub("", s)
    s = re.sub(r"\bBPM\b", "", s, flags=re.I)  # dangling BPM
    return re.sub(r"\s{2,}", " ", s).strip(" -_.")


def normalize_caps_allcaps_to_lower(s: str) -> str:
    # any fully uppercase word (>=2 letters) -> lowercase
    return UPPERWORD_RE.sub(lambda m: m.group(0).lower(), s)


def strip_brackets_and_parens(s: str) -> str:
    # kill explicit empty []
    s = re.sub(r"\[\s*\]", "", s)
    # remove brackets/parens that carry no letters/digits (pure punctuation)
    s = re.sub(r"\((?:\s|[^\w])*\)", "", s)
    s = re.sub(r"\[(?:\s|[^\w])*\]", "", s)
    s = re.sub(r"\{(?:\s|[^\w])*\}", "", s)
    # remove stray bracket chars
    s = re.sub(r"[\[\]{}()]+", "", s)
    return s


def ascii_fold(s: str) -> str:
    try:
        import unicodedata

        return (
            unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        )
    except Exception:
        return s


# -----------------------------
# Core cleaning
# -----------------------------


def clean_piece(s: str) -> str:
    """Clean a segment (artist or title) aggressively but safely."""
    s = JUNK_RE.sub("", s)
    s = strip_brackets_and_parens(s)
    s = strip_bpm_tokens(s)
    s = normalize_chars(s)
    s = normalize_caps_allcaps_to_lower(s)
    s = re.sub(r"\s+", " ", s).strip(" -_.\t")
    return s


def split_dash_parts(name: str) -> List[str]:
    return [p.strip() for p in name.split(" - ") if p.strip()]


def drop_trailing_labelish(parts: List[str]) -> List[str]:
    if len(parts) >= 3 and LABEL_HINTS.search(parts[-1]):
        return parts[:-1]
    return parts


def collapse_duplicate_artist(parts: List[str]) -> List[str]:
    # handle "Artist - ARTIST - Title" (case-insensitive dup)
    if len(parts) >= 3:
        a, b = parts[0], parts[1]
        if a and b and a.strip().lower() == b.strip().lower():
            return [a] + parts[2:]
    return parts


def remove_track_prefix_in_title(s: str) -> str:
    # titles like "Track 09 - Stormerr!" → "Stormerr!"
    return re.sub(r"^\s*track\s*\d+\s*-\s*", "", s, flags=re.I)


def guess_artist_title(basename: str) -> Tuple[str, str, str]:
    """
    Returns (trackno, artist, title)
    Accepts patterns:
      "NN - Artist - Title - MaybeLabel"
      "NN - Title - Artist"
      "Artist - Title"
      "Title - Artist"
    Heuristics drop trailing label-ish token and collapse duplicated artist.
    """
    trackno = ""
    name = basename

    # leading track number
    m = re.match(r"^\s*(\d{1,3})\s*-\s*(.*)$", name)
    if m:
        trackno, name = m.group(1), m.group(2)

    parts = split_dash_parts(name)
    parts = drop_trailing_labelish(parts)
    parts = collapse_duplicate_artist(parts)

    if len(parts) >= 2:
        a, b = parts[0], parts[1]
        # If second looks like a longer phrase, assume "Artist - Title"
        if len(b) >= len(a):
            artist, title = a, " - ".join(parts[1:])
        else:
            # maybe "Title - Artist"
            artist, title = parts[-1], " - ".join(parts[:-1])
    else:
        artist, title = "", parts[0] if parts else basename

    artist = clean_piece(artist)
    title = clean_piece(remove_track_prefix_in_title(title))

    # if one side ended up empty, fall back to the other
    if not artist and title:
        # try to pull artist from end of title when it looks like "... - Artist"
        tail_parts = split_dash_parts(title)
        if len(tail_parts) >= 2:
            artist = clean_piece(tail_parts[-1])
            title = clean_piece(" - ".join(tail_parts[:-1]))

    return trackno, artist, title


def safe_filename(s: str, ascii_only: bool) -> str:
    for pat, repl in SAFE_REPLACE:
        s = re.sub(pat, repl, s)
    if ascii_only:
        s = ascii_fold(s)
    return s.strip()


def build_new_name(
    trackno: str, artist: str, title: str, ext: str, keep_track: bool = True
) -> str:
    prefix = f"{int(trackno):02d} - " if (keep_track and trackno.isdigit()) else ""
    stem = (
        f"{prefix}{artist} - {title}"
        if (artist and title)
        else f"{prefix}{title or 'track'}"
    )
    # normalize any double spaces/hyphens again
    stem = re.sub(r"\s{2,}", " ", stem).strip()
    return f"{stem}.{ext.lower()}"


def pair_image(old: Path) -> Path | None:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        cand = old.with_suffix(ext)
        if cand.exists():
            return cand
    return None


# -----------------------------
# Public API
# -----------------------------


def plan_renames(
    root: Path, ascii_only: bool, keep_track: bool
) -> List[tuple[Path, Path]]:
    """Return list of (old_path, new_path) actions under root."""
    audios: Iterable[Path] = (
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    )
    changes: List[tuple[Path, Path]] = []
    for p in audios:
        base = clean_piece(p.stem)
        trackno, artist, title = guess_artist_title(base)
        new_name = build_new_name(
            trackno, artist, title, p.suffix[1:], keep_track=keep_track
        )
        new_name = safe_filename(new_name, ascii_only)
        target = p.with_name(new_name)

        # avoid clobbering: if target exists and is a different file, append .N
        i = 1
        while target.exists() and target.resolve() != p.resolve():
            target = p.with_name(f"{Path(new_name).stem}.{i}{p.suffix}")
            i += 1

        if target.name != p.name:
            changes.append((p, target))
    return changes


def apply_changes(changes: List[tuple[Path, Path]], move_covers: bool, undo_csv: Path):
    """Apply planned renames; move matching images; write undo CSV."""
    undo_csv.parent.mkdir(parents=True, exist_ok=True)
    with undo_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["old_path", "new_path"])
        for old, new in changes:
            new.parent.mkdir(parents=True, exist_ok=True)
            if move_covers:
                img = pair_image(old)
                if img:
                    new_img = new.with_suffix(img.suffix)
                    j = 1
                    while new_img.exists() and new_img.resolve() != img.resolve():
                        new_img = new.with_name(f"{new.stem}.{j}{new_img.suffix}")
                        j += 1
                    shutil.move(str(img), str(new_img))
            shutil.move(str(old), str(new))
            w.writerow([str(old), str(new)])
