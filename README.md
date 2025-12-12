# Pawkit Transcript Service

A lightweight microservice that extracts YouTube video transcripts using yt-dlp.

## Endpoints

### GET /transcript?url={youtube_url}

Returns the transcript for a YouTube video.

**Example:**
```
GET /transcript?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

**Response:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Video Title",
  "channel": "Channel Name",
  "duration": 300,
  "transcript": "Full transcript text...",
  "length": 5000
}
```

**Errors:**
- `400` - Missing or invalid URL
- `404` - No English captions available
- `500` - Server error

### GET /health

Health check endpoint. Returns `{"status": "ok"}`.

## Deploy to Railway (Free)

1. Go to [railway.app](https://railway.app)
2. Sign in with GitHub
3. Click **"New Project"** → **"Deploy from GitHub repo"**
4. Select `pawkit-transcript-service`
5. Railway auto-detects Python and deploys
6. Click **"Generate Domain"** to get your public URL

## Local Development

```bash
pip install -r requirements.txt
python app.py
```

Service runs on http://localhost:8080

## How It Works

1. Receives a YouTube URL
2. Uses yt-dlp to extract video metadata and caption URLs
3. Fetches captions (prefers manual, falls back to auto-generated)
4. Parses and cleans the transcript text
5. Returns JSON with transcript and video info

## Why yt-dlp?

- Battle-tested and actively maintained
- Handles YouTube's anti-scraping measures
- Supports both manual and auto-generated captions
- Works on 1000+ video sites
