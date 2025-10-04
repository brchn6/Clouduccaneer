# CloudBuccaneer Web UI - Quick Start Guide

Get up and running with the CloudBuccaneer web interface in 60 seconds!

## Installation

```bash
# Clone the repository
git clone https://github.com/brchn6/Clouduccaneer.git
cd Clouduccaneer

# Install CloudBuccaneer
pip install -e .
```

## Launch Web UI

```bash
# Start the web server
cb web
```

You should see:
```
🌐 Starting CloudBuccaneer Web UI...
   Server: http://127.0.0.1:8080
   Press Ctrl+C to stop
```

## Access the Interface

Open your web browser and navigate to:
```
http://localhost:8080
```

## Quick Tutorial

### 1. Download a Track

1. Click on the **Download** tab (already selected by default)
2. Paste a SoundCloud or Spotify URL
3. (Optional) Set a custom destination folder
4. Click **Download**
5. Wait for the success message!

**Example URLs to try:**
- SoundCloud: `https://soundcloud.com/artist/track-name`
- Spotify: `https://open.spotify.com/track/...`

### 2. Search for Music

1. Click the **Search** tab
2. Enter an artist name or track title
3. Select search type (Tracks, Playlists, or Users)
4. Click **Search**
5. Browse results and click **Download** on any result

### 3. Clean Up Files

1. Click the **Rename** tab
2. Enter your music folder path (e.g., `~/Music`)
3. Click **Rename Files**
4. CloudBuccaneer will clean up messy filenames automatically!

### 4. Remove Leftover Files

1. Click the **Clean** tab
2. Enter folder path
3. Select what to remove (images, webp, temp files)
4. Click **Clean Folder**

### 5. Detect BPM

1. Click the **BPM Detect** tab
2. Enter a file path or folder path
3. Choose detection mode (advanced is more accurate)
4. Click **Detect BPM**
5. View BPM results for your audio files

## Tips

- 💡 The web UI uses the same configuration as the CLI
- 🎨 The interface is fully responsive - works on mobile too!
- ⚡ All operations run asynchronously - no page reloads
- 🔒 By default, only accessible from your computer (localhost)

## Need Help?

- Check the full documentation: `WEB_UI.md`
- View CLI documentation: `README.md`
- Report issues: [GitHub Issues](https://github.com/brchn6/Clouduccaneer/issues)

## Legal Notice

⚠️ **For personal use only.** Only download content you have the right to access. Respect copyright laws and terms of service of content platforms.

---

**Enjoy using CloudBuccaneer!** ☁️🏴‍☠️
