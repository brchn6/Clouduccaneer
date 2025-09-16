# cb/cli.py
from __future__ import annotations
import json
import typer
from pathlib import Path
from typing import Optional, Dict, List
from .utils import load_config
from . import ytwrap
from .renamer import plan_renames, apply_changes
from . import spotwrap
from .bpm import BPMDetector, find_audio_files, format_bpm_result, add_bpm_to_filename, add_bpm_to_tags

app = typer.Typer(help="CloudBuccaneer — fetch + fix SoundCloud and Spotify downloads")


@app.command()
def fetch(url: str,
          dest: Path = typer.Option(None, "--dest", help="Destination directory"),
          limit_seconds: int = typer.Option(None, "--max-seconds", 
                                           help="Skip tracks longer than this"),
          dry: bool = typer.Option(False, "--dry", help="Print what would be done")):
    """Download a playlist/track/user/likes/reposts with yt-dlp using sane defaults."""
    cfg = load_config()
    base = Path(dest or cfg["download_dir"]).expanduser()
    base.mkdir(parents=True, exist_ok=True)

    # When limiting by duration, enumerate track urls first
    if limit_seconds is not None:
        urls = list(ytwrap.print_lines([
            "yt-dlp", "--flat-playlist", "--print", "%(url)s", url
        ]))
        dmap = ytwrap.duration_map(urls)
        urls = [u for u in urls if 0 < dmap.get(u, 0) < limit_seconds]
        if dry:
            for u in urls:
                print("[DRY] would fetch:", u)
            return
        for u in urls:
            ytwrap.fetch(u, str(base / cfg["out_template"]))
    else:
        if dry:
            print("[DRY] would fetch:", url)
            return
        ytwrap.fetch(url, str(base / cfg["out_template"]))


@app.command()
def rename(folder: Path = typer.Argument(..., help="Folder to clean"),
           ascii_only: bool = typer.Option(None, "--ascii/--no-ascii"),
           keep_track: bool = typer.Option(None, "--keep-track/--no-keep-track"),
           move_covers: bool = typer.Option(False, "--move-covers"),
           apply: bool = typer.Option(False, "--apply"),
           undo: Path = typer.Option(Path("undo_cloudbuccaneer.csv"), "--undo")):
    """Clean filenames: strip junk; guess artist/title; keep track # optionally; move covers."""
    cfg = load_config()
    if ascii_only is None:
        ascii_only = bool(cfg["rename"].get("ascii", True))
    if keep_track is None:
        keep_track = bool(cfg["rename"].get("keep_track", True))
    changes = plan_renames(folder.expanduser(), ascii_only=ascii_only, 
                          keep_track=keep_track)
    if not changes:
        print("Nothing to change.")
        raise typer.Exit(code=0)
    for old, new in changes:
        print(f"[{'APPLY' if apply else 'DRY'}] {old} -> {new}")
    if apply:
        apply_changes(
            changes,
            move_covers=move_covers or bool(cfg["rename"].get("move_covers", False)),
            undo_csv=undo.expanduser()
        )

@app.command()
def dedupe(root: Path = typer.Argument(..., help="Kill *.1.mp3 style dupes"),
           apply: bool = typer.Option(False, "--apply")):
    """Remove simple duplicate files that end with .1 before the extension."""
    root = root.expanduser()
    victims = list(p for p in root.rglob("*") 
                   if p.is_file() and p.suffix.lower() == ".mp3" and 
                   p.stem.endswith(".1"))
    for v in victims:
        print(f"[{'DELETE' if apply else 'DRY'}] {v}")
        if apply:
            v.unlink()


@app.command()
def search(query: str,
           max: int = typer.Option(20, "--max", help="Max results to take"),
           kind: str = typer.Option("tracks", "--kind", 
                                   help="'tracks' (default), 'sets', or 'users'"),
           cluster: bool = typer.Option(False, "--cluster", 
                                       help="Group results by uploader"),
           dest: Path = typer.Option(None, "--dest", help="Destination directory"),
           max_seconds: Optional[int] = typer.Option(None, "--max-seconds", 
                                                    help="Skip tracks longer than this"),
           dry: bool = typer.Option(False, "--dry", help="Preview without downloading")):
    """
    Search SoundCloud via yt-dlp's scsearch and (optionally) cluster by uploader.
    """
    cfg = load_config()
    base = Path(dest or cfg["download_dir"]).expanduser()
    base.mkdir(parents=True, exist_ok=True)

    if cluster:
        pairs = ytwrap.sc_search_url_title_pairs(query, kind=kind, max_results=max)
        if not pairs:
            print("No results."); raise typer.Exit(code=1)
        # group by uploader
        buckets: Dict[str, List[str]] = {}
        for url, uploader in pairs:
            buckets.setdefault(uploader or "unknown", []).append(url)

        print(f"Found {sum(len(v) for v in buckets.values())} result(s) in {len(buckets)} bucket(s).")
        for uploader, urls in buckets.items():
            print(f"\n[uploader: {uploader}] {len(urls)} item(s)")
            if dry:
                for u in urls: print("  ", u)
            else:
                out_tmpl = str(base / uploader / cfg.get("out_template", "%(title)s - %(artist|uploader)s.%(ext)s"))
                ytwrap.fetch_many(urls, out_tmpl, max_seconds=max_seconds, write_thumb=False)
        return

    # non-clustered path
    urls = ytwrap.sc_search_urls(query, kind=kind, max_results=max)
    if not urls:
        print("No results."); raise typer.Exit(code=1)
    print(f"Found {len(urls)} result(s).")
    out_tmpl = str(base / cfg.get("out_template", "%(title)s - %(artist|uploader)s.%(ext)s"))
    ytwrap.fetch_many(urls, out_tmpl, max_seconds=max_seconds, dry=dry, write_thumb=False)

@app.command("cluster-user")
def cluster_user(user_url: str,
                 dest: Path = typer.Option(None, "--dest", help="Base destination directory"),
                 dry: bool = typer.Option(False, "--dry", help="List only (no download)")):
    """
    Cluster a user's public content into uploads / reposts / likes / sets using canonical URLs.
    """
    cfg = load_config()
    base = Path(dest or cfg["download_dir"]).expanduser()
    base.mkdir(parents=True, exist_ok=True)

    # normalize user root like https://soundcloud.com/<handle>
    user_root = user_url.rstrip('/')
    buckets = {
        "uploads": f"{user_root}/tracks",
        "reposts": f"{user_root}/reposts",
        "likes":   f"{user_root}/likes",
        "sets":    f"{user_root}/sets",
    }

    total = 0
    for name, url in buckets.items():
        urls = ytwrap.list_flat(url)
        total += len(urls)
        print(f"[{name}] {len(urls)} item(s) :: {url}")
        if dry:
            for u in urls[:10]: print("  ", u)
            if len(urls) > 10: print("  ...")
        else:
            out_tmpl = str(base / Path(user_root).name / name / cfg.get("out_template", "%(title)s - %(artist|uploader)s.%(ext)s"))
            ytwrap.fetch_many(urls, out_tmpl, write_thumb=False)
    print(f"\nTotal items across buckets: {total}")

@app.command("fetch-user")
def fetch_user(user_url: str,
               kind: str = typer.Option("uploads", "--kind", help="'uploads'|'reposts'|'likes'|'sets'"),
               dest: Path = typer.Option(None, "--dest"),
               max_seconds: Optional[int] = typer.Option(None, "--max-seconds"),
               limit: Optional[int] = typer.Option(None, "--limit", help="Only take the most recent N items"),
               dry: bool = typer.Option(False, "--dry")):
    cfg = load_config()
    base = Path(dest or cfg["download_dir"]).expanduser(); base.mkdir(parents=True, exist_ok=True)

    root = ytwrap.normalize_user_root(user_url)
    path_map = {
        "uploads": f"{root}/tracks",
        "reposts": f"{root}/reposts",
        "likes":   f"{root}/likes",
        "sets":    f"{root}/sets",
    }
    if kind not in path_map:
        print("Invalid --kind. Use uploads|reposts|likes|sets"); raise typer.Exit(2)

    urls = ytwrap.list_flat(path_map[kind])
    if limit:   # <- take only most recent N
        urls = urls[:limit]

    print(f"{kind}: {len(urls)} item(s)")
    out_tmpl = str(base / Path(root).name / kind / cfg.get("out_template", "%(title)s - %(artist|uploader)s.%(ext)s"))
    ytwrap.fetch_many(urls, out_tmpl, max_seconds=max_seconds, dry=dry, write_thumb=False)


@app.command()
def clean(folder: Path = typer.Argument(..., help="Folder to sweep"),
          images: bool = typer.Option(True, "--images/--no-images", help="Remove leftover image files"),
          parts: bool = typer.Option(True, "--parts/--no-parts", help="Remove temp/partial files"),
          webp: bool = typer.Option(True, "--webp/--no-webp", help="Remove webp thumbnails")):
    """
    Remove common leftover files (thumbnails, partials) after downloads.
    """
    folder = folder.expanduser()
    if not folder.is_dir():
        print("Not a directory:", folder); raise typer.Exit(code=2)

    patterns = []
    if images:
        patterns += ["*.jpg", "*.jpeg", "*.png"]
    if webp:
        patterns += ["*.webp"]
    if parts:
        patterns += ["*.part", "*.temp"]

    removed = 0
    for pat in patterns:
        for p in folder.rglob(pat):
            try:
                p.unlink()
                removed += 1
            except Exception as e:
                print("Skip (error):", p, e)


@app.command("fetch-spotify")
def fetch_spotify(url: str,
                 dest: Path = typer.Option(None, "--dest", help="Destination directory"),
                 quality: str = typer.Option("320k", "--quality", help="Audio quality (320k, 256k, 192k, 128k)"),
                 format: str = typer.Option("mp3", "--format", help="Audio format (mp3, flac, ogg, m4a)"),
                 lyrics: bool = typer.Option(True, "--lyrics/--no-lyrics", help="Download lyrics"),
                 dry: bool = typer.Option(False, "--dry", help="Print what would be done")):
    """Download a Spotify track/playlist/album with spotdl."""
    if not spotwrap.validate_spotify_url(url):
        print("Error: Invalid Spotify URL"); raise typer.Exit(code=1)
    
    cfg = load_config()
    base = Path(dest or cfg.get("spotify", {}).get("download_dir", "~/Download/spotify")).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    
    url = spotwrap.normalize_spotify_url(url)
    
    if dry:
        print(f"[DRY] would fetch spotify: {url}")
        print(f"[DRY] destination: {base}")
        print(f"[DRY] quality: {quality}, format: {format}")
        return
    
    # Use a template that works with spotdl
    out_template = str(base / "{artist} - {title}.{ext}")
    spotwrap.fetch(url, out_template, audio_fmt=format, quality=quality, lyrics=lyrics)

@app.command("search-spotify")  
def search_spotify(query: str,
                  max: int = typer.Option(20, "--max", help="Max results"),
                  type_filter: str = typer.Option("track", "--type", help="Search type: track, album, playlist, artist"),
                  dest: Path = typer.Option(None, "--dest", help="Destination directory"), 
                  quality: str = typer.Option("320k", "--quality", help="Audio quality"),
                  format: str = typer.Option("mp3", "--format", help="Audio format"),
                  dry: bool = typer.Option(False, "--dry", help="Preview without downloading")):
    """Search and download from Spotify."""
    cfg = load_config()
    base = Path(dest or cfg.get("spotify", {}).get("download_dir", "~/Download/spotify")).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    
    # For now, use the query directly with spotdl since it can handle search queries
    search_query = f"{type_filter}:{query}" if type_filter != "track" else query
    
    if dry:
        print(f"[DRY] would search spotify for: {search_query}")
        print(f"[DRY] destination: {base}")
        return
    
    out_template = str(base / "{artist} - {title}.{ext}")
    spotwrap.fetch(search_query, out_template, audio_fmt=format, quality=quality)

@app.command()
def summarize(
    conversation: str = typer.Argument(..., help="Conversation input as JSON string or file path"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file for summary")):
    """
    Create a detailed summary from a series of user/assistant message pairs.
    Conversation can be provided as JSON string or file path.
    """
    try:
        # Try to load as file path first
        conv_path = Path(conversation)
        if conv_path.exists():
            with conv_path.open('r', encoding='utf-8') as f:
                conversation_data = json.load(f)
        else:
            # Try to parse as JSON string
            conversation_data = json.loads(conversation)
    except (json.JSONDecodeError, FileNotFoundError):
        print("Error: Invalid JSON format or file not found.")
        raise typer.Exit(code=1)
    
    # Validate conversation structure
    if not isinstance(conversation_data, list):
        print("It seems that the conversation you intended to provide is incomplete. Please provide the full series of user/assistant message pairs so I can create a detailed summary for you.")
        raise typer.Exit(code=1)
    
    # Check if conversation contains valid message pairs
    valid_pairs = 0
    for item in conversation_data:
        if isinstance(item, dict) and 'role' in item and 'content' in item:
            if item['role'] in ['user', 'assistant'] and item['content'].strip():
                valid_pairs += 1
    
    if valid_pairs < 2:  # Need at least one user and one assistant message
        print("It seems that the conversation you intended to provide is incomplete. Please provide the full series of user/assistant message pairs so I can create a detailed summary for you.")
        raise typer.Exit(code=1)
    
    # Create summary
    summary = _create_conversation_summary(conversation_data)
    
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('w', encoding='utf-8') as f:
            f.write(summary)
        print(f"Summary written to: {output}")
    else:
        print(summary)

def _create_conversation_summary(conversation_data: List[Dict]) -> str:
    """Generate a detailed summary from conversation data."""
    user_messages = []
    assistant_messages = []
    
    for msg in conversation_data:
        if msg.get('role') == 'user' and msg.get('content', '').strip():
            user_messages.append(msg['content'].strip())
        elif msg.get('role') == 'assistant' and msg.get('content', '').strip():
            assistant_messages.append(msg['content'].strip())
    
    summary_lines = [
        "# Conversation Summary",
        "",
        f"**Total Messages:** {len(conversation_data)}",
        f"**User Messages:** {len(user_messages)}",
        f"**Assistant Messages:** {len(assistant_messages)}",
        "",
        "## Key Topics Discussed:",
    ]
    
    # Extract key topics from user messages
    topics = set()
    for msg in user_messages[:5]:  # Look at first 5 user messages for topics
        words = msg.lower().split()
        # Simple keyword extraction
        for word in words:
            if len(word) > 4 and word.isalpha():
                topics.add(word)
    
    for topic in sorted(list(topics)[:10]):  # Limit to 10 topics
        summary_lines.append(f"- {topic.title()}")
    
    summary_lines.extend([
        "",
        "## Conversation Flow:",
        f"The conversation began with user asking about {user_messages[0][:50] + '...' if len(user_messages[0]) > 50 else user_messages[0]}",
    ])
    
    if len(assistant_messages) > 0:
        summary_lines.append(f"Assistant responded with {assistant_messages[0][:50] + '...' if len(assistant_messages[0]) > 50 else assistant_messages[0]}")
    
    if len(user_messages) > 1:
        summary_lines.append(f"The conversation continued with {len(user_messages) - 1} additional user message(s).")
    
    return "\n".join(summary_lines)

@app.command()
def bpm(target: Path = typer.Argument(..., help="Audio file or directory to analyze"),
        parallel: bool = typer.Option(False, "--parallel", help="Use parallel processing for multiple files"),
        advanced: bool = typer.Option(True, "--advanced/--basic", help="Use advanced multi-method detection"),
        recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Search subdirectories"),
        export_filename: bool = typer.Option(False, "--export-filename", help="Add BPM to filename (e.g., song [128 BPM].mp3)"),
        export_tags: bool = typer.Option(False, "--export-tags", help="Add BPM to audio file metadata tags"),
        backup: bool = typer.Option(True, "--backup/--no-backup", help="Keep original files when exporting to filename")):
    """Analyze audio files and detect their BPM (beats per minute)."""
    target = target.expanduser()
    
    if not target.exists():
        print(f"Error: Path does not exist: {target}")
        raise typer.Exit(code=1)
    
    detector = BPMDetector(use_advanced=advanced)
    
    if target.is_file():
        # Single file processing
        if not detector.is_supported_format(target):
            print(f"Error: Unsupported file format: {target.suffix}")
            print(f"Supported formats: {', '.join(sorted(detector.SUPPORTED_FORMATS))}")
            raise typer.Exit(code=1)
        
        print(f"Analyzing: {target.name}")
        bpm = detector.detect_bpm(target)
        print(format_bpm_result(target, bpm))
        
        # Export options
        if bpm is not None:
            if export_filename:
                new_path = add_bpm_to_filename(target, bpm, backup=backup)
                if new_path:
                    print(f"Exported to filename: {new_path.name}")
                else:
                    print("Failed to export to filename")
            
            if export_tags:
                success = add_bpm_to_tags(target, bpm)
                if success:
                    print("Added BPM to metadata tags")
                else:
                    print("Failed to add BPM to metadata tags")
        
    elif target.is_dir():
        # Directory processing
        audio_files = find_audio_files(target, recursive=recursive)
        
        if not audio_files:
            print(f"No supported audio files found in: {target}")
            print(f"Supported formats: {', '.join(sorted(detector.SUPPORTED_FORMATS))}")
            raise typer.Exit(code=0)
        
        print(f"Found {len(audio_files)} audio file(s) in: {target}")
        if len(audio_files) > 1 and parallel:
            print("Using parallel processing...")
        
        # Detect BPM for all files
        results = detector.detect_bpm_batch(audio_files, parallel=parallel)
        
        # Display results and export
        print()
        exported_filenames = 0
        exported_tags = 0
        
        for file_path, bpm in results.items():
            print(format_bpm_result(file_path, bpm))
            
            # Export options
            if bpm is not None:
                if export_filename:
                    new_path = add_bpm_to_filename(file_path, bpm, backup=backup)
                    if new_path:
                        exported_filenames += 1
                
                if export_tags:
                    success = add_bpm_to_tags(file_path, bpm)
                    if success:
                        exported_tags += 1
            
        # Summary
        successful = sum(1 for bpm in results.values() if bpm is not None)
        print(f"\nSummary: {successful}/{len(audio_files)} files analyzed successfully")
        
        if export_filename:
            print(f"Exported to filename: {exported_filenames}/{successful} files")
        if export_tags:
            print(f"Added to metadata tags: {exported_tags}/{successful} files")
            
    else:
        print(f"Error: Invalid target type: {target}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
