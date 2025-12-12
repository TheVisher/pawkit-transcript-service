from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp
import re
import json
import urllib.request

app = Flask(__name__)
CORS(app)

def extract_video_id(url):
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/shorts\/([^&\n?#]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def decode_html_entities(text):
    """Decode common HTML entities in transcript text."""
    text = text.replace('&amp;', '&')
    text = text.replace('&#39;', "'")
    text = text.replace('&quot;', '"')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ')
    return text

def parse_segments_from_json3(caption_json):
    """Parse JSON3 format captions into timestamped segments."""
    segments = []
    for event in caption_json.get('events', []):
        start_ms = event.get('tStartMs', 0)
        duration_ms = event.get('dDurationMs', 0)

        segs = event.get('segs', [])
        text_parts = []
        for seg in segs:
            text = seg.get('utf8', '').strip()
            if text and text != '\n':
                text_parts.append(text)

        text = ' '.join(text_parts).strip()
        if text:
            segments.append({
                'start': start_ms / 1000,  # Convert to seconds
                'duration': duration_ms / 1000,
                'text': decode_html_entities(text)
            })
    return segments

def parse_segments_from_xml(caption_content):
    """Parse XML/SRV3 format captions into timestamped segments."""
    segments = []
    matches = re.findall(r'<text start="([\d.]+)"[^>]*dur="([\d.]+)"[^>]*>([^<]*)</text>', caption_content)
    for start, dur, text in matches:
        text = text.strip()
        if text:
            segments.append({
                'start': float(start),
                'duration': float(dur),
                'text': decode_html_entities(text)
            })
    return segments

def group_segments(segments, interval=30):
    """Group segments into chunks of approximately `interval` seconds."""
    if not segments:
        return []

    grouped = []
    current_group = None

    for seg in segments:
        group_start = int(seg['start'] // interval) * interval

        if current_group is None or current_group['start'] != group_start:
            if current_group:
                grouped.append(current_group)
            current_group = {
                'start': group_start,
                'end': seg['start'] + seg['duration'],
                'text': seg['text']
            }
        else:
            current_group['text'] += ' ' + seg['text']
            current_group['end'] = seg['start'] + seg['duration']

    if current_group:
        grouped.append(current_group)

    return grouped

@app.route('/transcript', methods=['GET'])
def get_transcript():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Missing url parameter'}), 400

    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    try:
        ydl_opts = {
            'skip_download': True,
            'writeautomaticsub': True,
            'writesubtitles': True,
            'subtitleslangs': ['en', 'en-US', 'en-GB'],
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)

            # Try manual captions first, then auto-generated
            captions = info.get('subtitles', {}) or {}
            auto_captions = info.get('automatic_captions', {}) or {}

            # Find English captions
            caption_data = None
            for lang in ['en', 'en-US', 'en-GB', 'en-orig']:
                if lang in captions:
                    caption_data = captions[lang]
                    break

            # Fallback to auto-captions
            if not caption_data:
                for lang in ['en', 'en-US', 'en-GB', 'en-orig']:
                    if lang in auto_captions:
                        caption_data = auto_captions[lang]
                        break

            if not caption_data:
                available = list(captions.keys()) + list(auto_captions.keys())
                return jsonify({
                    'error': 'No English captions available',
                    'available_languages': available
                }), 404

            # Get the JSON3 format URL (best for parsing with timestamps)
            caption_url = None
            is_json3 = False
            for fmt in caption_data:
                if fmt.get('ext') == 'json3':
                    caption_url = fmt.get('url')
                    is_json3 = True
                    break

            if not caption_url:
                caption_url = caption_data[0].get('url')

            if not caption_url:
                return jsonify({'error': 'Could not get caption URL'}), 500

            # Fetch the actual captions
            with urllib.request.urlopen(caption_url) as response:
                caption_content = response.read().decode()

            # Parse segments with timestamps
            segments = []
            if is_json3:
                try:
                    caption_json = json.loads(caption_content)
                    segments = parse_segments_from_json3(caption_json)
                except json.JSONDecodeError:
                    segments = parse_segments_from_xml(caption_content)
            else:
                segments = parse_segments_from_xml(caption_content)

            # Group segments into ~30 second chunks for cleaner display
            grouped_segments = group_segments(segments, interval=30)

            # Build flat transcript from grouped segments
            flat_transcript = ' '.join([s['text'] for s in grouped_segments])
            flat_transcript = re.sub(r'\s+', ' ', flat_transcript).strip()

            return jsonify({
                'video_id': video_id,
                'title': info.get('title'),
                'channel': info.get('channel'),
                'duration': info.get('duration'),
                'transcript': flat_transcript[:15000],
                'segments': grouped_segments,  # NEW: timestamped segments
                'length': len(flat_transcript)
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
