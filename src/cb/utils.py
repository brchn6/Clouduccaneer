# cb/utils.py
from __future__ import annotations
import yaml, os
from pathlib import Path
from typing import Any, Dict

def load_config() -> Dict[str, Any]:
    # order: env var -> ~/.config/cloudbuccaneer/config.yaml -> defaults
    cfg_path = Path(os.environ.get("CB_CONFIG", "~/.config/cloudbuccaneer/config.yaml")).expanduser()
    default = {
        "download_dir": str(Path("~/Download/soundcloud").expanduser()),
        "out_template": "%(playlist_title|Unknown Set)s/%(playlist_index|0)02d - %(title)s - %(artist|uploader)s.%(ext)s",
        "rename": {"ascii": True, "keep_track": True, "move_covers": True}
    }
    if cfg_path.exists():
        with cfg_path.open() as f: user = yaml.safe_load(f) or {}
        default.update(user or {})
    return default
