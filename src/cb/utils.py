# cb/utils.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

import yaml


def load_config() -> Dict[str, Any]:
    # order: env var -> ~/.config/cloudbuccaneer/config.yaml -> defaults
    cfg_path = Path(
        os.environ.get("CB_CONFIG", "~/.config/cloudbuccaneer/config.yaml")
    ).expanduser()
    default = {
        "download_dir": str(Path("~/Download/soundcloud").expanduser()),
        "out_template": (
            "%(playlist_title|Unknown Set)s/"
            "%(playlist_index|0)02d - %(title)s - "
            "%(artist|uploader)s.%(ext)s"
        ),
        "rename": {"ascii": True, "keep_track": True, "move_covers": True},
        "spotify": {
            "download_dir": str(Path("~/Download/spotify").expanduser()),
            "quality": "320k",
            "format": "mp3",
            "lyrics": True,
            "playlist_numbering": True,
        },
    }
    if cfg_path.exists():
        with cfg_path.open() as f:
            user = yaml.safe_load(f) or {}
        default.update(user or {})
    return default


def print_download_summary(
    platform: str,
    successful: int,
    total: int,
    failed_items: List[str] = None,
    destination: Path = None,
    format_info: str = None,
    additional_info: Dict[str, Any] = None
) -> None:
    """Print a comprehensive download summary for any platform."""
    print(f"\n{'='*60}")
    print(f"  {platform.upper()} DOWNLOAD SUMMARY")
    print(f"{'='*60}")

    # Basic stats
    print(f"📊 Statistics:")
    print(f"   ✓ Successful downloads: {successful}")
    print(f"   ✗ Failed downloads: {total - successful}")
    print(f"   📁 Total processed: {total}")

    if total > 0:
        success_rate = (successful / total) * 100
        print(f"   📈 Success rate: {success_rate:.1f}%")

    # Destination info
    if destination:
        print(f"\n📂 Destination: {destination}")

    # Format info
    if format_info:
        print(f"🎵 Format: {format_info}")

    # Failed items (limited display)
    if failed_items:
        print(f"\n❌ Failed items ({len(failed_items)}):")
        for item in failed_items[:3]:  # Show first 3
            print(f"   - {item}")
        if len(failed_items) > 3:
            print(f"   ... and {len(failed_items) - 3} more")

    # Additional platform-specific info
    if additional_info:
        print(f"\nℹ️  Additional info:")
        for key, value in additional_info.items():
            print(f"   {key}: {value}")

    print(f"{'='*60}\n")


def print_quick_summary(platform: str, successful: int, total: int) -> None:
    """Print a quick one-line summary."""
    if total == 0:
        print(f"[{platform}] No items to process")
    elif successful == total:
        print(f"[{platform}] ✓ All {total} downloads completed successfully")
    else:
        failed = total - successful
        print(f"[{platform}] Completed: {successful}/{total} successful, {failed} failed")
