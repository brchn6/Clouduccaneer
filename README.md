# /home/barc/dev/CloudBuccaneer
# CloudBuccaneer

Fetch + fix SoundCloud and Spotify downloads. Wraps `yt-dlp` for SoundCloud and `spotdl` for Spotify, then cleans filenames with smart heuristics. **Now includes high-quality BPM detection for audio analysis!**

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

### BPM Detection (NEW!)
```bash
cb bpm song.mp3           # Detect BPM of a single file
cb bpm music_folder/      # Analyze all audio files in folder
cb bpm folder/ --parallel # Use parallel processing for faster batch analysis
cb bpm folder/ --basic    # Use basic detection (faster, less accurate)

# Export options (NEW!)
cb bpm song.mp3 --export-filename    # Add BPM to filename: song [128 BPM].mp3
cb bpm song.mp3 --export-tags        # Add BPM to audio metadata tags  
cb bpm folder/ --export-filename --no-backup  # Export and remove originals
```

## BPM Detection Features

- **High Accuracy**: Uses librosa with advanced multi-method detection for reliable results
- **Multiple Formats**: Supports MP3, WAV, FLAC, M4A, OGG, AIFF, AU
- **Batch Processing**: Analyze entire folders with optional parallel processing  
- **Flexible Options**: Choose between advanced (accurate) or basic (fast) detection modes
- **Recursive Search**: Automatically finds audio files in subdirectories
- **Clear Output**: Shows results in format: `Track: song.mp3 → BPM: 128.5`
- **Export Options**: Add BPM to filenames or metadata tags for organization

### BPM Detection Examples
```bash
# Single file analysis
cb bpm "track.mp3"
# Output: Track: track.mp3 → BPM: 128.5

# Analyze all audio files in folder
cb bpm ~/Music/
# Output: Found 15 audio file(s) in: /home/user/Music
#         Track: song1.mp3 → BPM: 120.3
#         Track: song2.wav → BPM: 140.7
#         Summary: 15/15 files analyzed successfully

# Fast batch processing with parallel processing
cb bpm ~/Music/ --parallel

# Basic detection for speed (less accurate but faster)
cb bpm ~/Music/ --basic

# Analyze only current directory (no subdirectories)
cb bpm ~/Music/ --no-recursive

# Export BPM to filenames (creates "song [128 BPM].mp3")
cb bpm ~/Music/ --export-filename

# Add BPM to metadata tags (MP3, FLAC, M4A, OGG)
cb bpm ~/Music/ --export-tags

# Export to filenames without keeping originals
cb bpm ~/Music/ --export-filename --no-backup
```