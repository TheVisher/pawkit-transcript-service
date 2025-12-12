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
            
            # Get the JSON3 format URL (best for parsing)
            caption_url = None
            for fmt in caption_data:
                if fmt.get('ext') == 'json3':
                    caption_url = fmt.get('url')
                    break
            
            if not caption_url:
                caption_url = caption_data[0].get('url')
            
            if not caption_url:
                return jsonify({'error': 'Could not get caption URL'}), 500
            
            # Fetch the actual captions
            with urllib.request.urlopen(caption_url) as response:
                caption_content = response.read().decode()
            
            # Try to parse as JSON3 format
            transcript_parts = []
            try:
                caption_json = json.loads(caption_content)
                for event in caption_json.get('events', []):
                    segs = event.get('segs', [])
                    for seg in segs:
                        text = seg.get('utf8', '').strip()
                        if text and text != '\n':
                            transcript_parts.append(text)
            except json.JSONDecodeError:
                # Fall back to XML/SRV3 parsing
                matches = re.findall(r'<text[^>]*>([^<]*)</text>', caption_content)
                transcript_parts = [m.strip() for m in matches if m.strip()]
            
            transcript = ' '.join(transcript_parts)
            transcript = re.sub(r'\s+', ' ', transcript).strip()
            
            # Decode HTML entities
            transcript = transcript.replace('&amp;', '&')
            transcript = transcript.replace('&#39;', "'")
            transcript = transcript.replace('&quot;', '"')
            transcript = transcript.replace('&lt;', '<')
            transcript = transcript.replace('&gt;', '>')
            
            return jsonify({
                'video_id': video_id,
                'title': info.get('title'),
                'channel': info.get('channel'),
                'duration': info.get('duration'),
                'transcript': transcript[:15000],
                'length': len(transcript)
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
