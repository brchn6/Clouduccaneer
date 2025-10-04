# CloudBuccaneer Web UI

A modern, clean web interface for CloudBuccaneer that provides easy access to all features through your browser.

## Quick Start

1. Install CloudBuccaneer:
```bash
pip install -e .
```

2. Start the web server:
```bash
cb web
```

3. Open your browser to `http://localhost:8080`

## Features

### 🎵 Download Music
Download tracks, playlists, and albums from:
- **SoundCloud**: Tracks, playlists, user uploads, likes, and reposts
- **Spotify**: Tracks, albums, and playlists with high-quality audio

Simply paste a URL and click Download!

### 🔍 Search
Search for music on SoundCloud:
- Search for tracks, playlists, or users
- Browse results with direct download buttons
- Quickly add results to your download queue

### ✏️ Rename Files
Clean up messy filenames automatically:
- Removes junk characters and formatting
- Intelligently extracts artist and title
- Handles track numbers and covers
- Uses smart heuristics for best results

### 🧹 Clean Folders
Remove leftover files after downloads:
- Thumbnail images (jpg, png, webp)
- Temporary/partial files (.part, .temp)
- Configurable cleanup options

### 🎵 BPM Detection
Analyze audio files and detect beats per minute:
- High accuracy using librosa
- Advanced or basic detection modes
- Batch processing for entire folders
- Parallel processing support for speed
- Results displayed in clear format

### ⚙️ Configuration
View your current CloudBuccaneer settings:
- Download directories
- Output templates
- Rename settings
- Spotify configuration

## Command Line Options

```bash
# Start on default host/port (127.0.0.1:8080)
cb web

# Bind to all interfaces
cb web --host 0.0.0.0

# Use custom port
cb web --port 3000

# Combine options
cb web --host 0.0.0.0 --port 8080
```

## Architecture

The web UI is built with:
- **Backend**: FastAPI (Python async web framework)
- **Frontend**: Vanilla JavaScript (no heavy frameworks)
- **Styling**: Custom CSS with modern design
- **Communication**: RESTful JSON API

### API Endpoints

- `GET /` - Main web interface
- `GET /api/config` - Get current configuration
- `POST /api/fetch` - Download from URL
- `POST /api/search` - Search SoundCloud
- `POST /api/rename` - Rename files in folder
- `POST /api/clean` - Clean leftover files
- `POST /api/bpm` - Detect BPM of audio files

## Security Notes

⚠️ **Important**: The web UI is designed for **local use only**. 

- By default, it binds to `127.0.0.1` (localhost only)
- If you bind to `0.0.0.0` or expose to network, ensure proper firewall rules
- No authentication is built-in - use behind reverse proxy if needed
- Only download content you have rights to access

## Troubleshooting

### Port Already in Use
If port 8080 is already taken:
```bash
cb web --port 8081
```

### Cannot Access from Other Devices
To allow access from other devices on your network:
```bash
cb web --host 0.0.0.0
```

### Static Files Not Loading
Make sure you installed CloudBuccaneer properly:
```bash
pip install -e .
```

## Development

The web UI code is located in:
- `src/cb/web/app.py` - FastAPI backend
- `src/cb/web/templates/index.html` - HTML interface
- `src/cb/web/static/css/style.css` - Styling
- `src/cb/web/static/js/app.js` - JavaScript functionality

## Screenshots

### Download Interface
![Download Interface](https://github.com/user-attachments/assets/3cee4295-f045-42fd-a614-f63411cfc520)

### Search Interface
![Search Interface](https://github.com/user-attachments/assets/cf5196df-2c9d-4802-9bf8-76383cf2c381)

### BPM Detection Interface
![BPM Detection](https://github.com/user-attachments/assets/fa079b2c-a673-450a-b041-51ac77cfb707)

## License

For personal use only. Respect copyright laws and terms of service.
