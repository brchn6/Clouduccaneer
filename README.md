# /home/barc/dev/CloudBuccaneer
# CloudBuccaneer

Fetch + fix SoundCloud and Spotify downloads. Wraps `yt-dlp` for SoundCloud and `spotdl` for Spotify, then cleans filenames with smart heuristics.

> Legal: Only download content you have the right to. This tool is for personal/offline use where permitted by law and by the site’s terms.

## Install
```bash
pip install -e .
```

## Usage 

### SoundCloud Downloads
```bash
cb fetch https://soundcloud.com/user/track
cb search "query" --cluster
```

### Spotify Downloads (NEW!)
```bash
cb fetch-spotify https://open.spotify.com/track/...
cb search-spotify "Bohemian Rhapsody" --type track
```

### General Commands
```bash
cb rename folder/         # Clean up filenames
cb clean folder/          # Remove leftover files
```