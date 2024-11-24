import logging
import os
import re
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from pytubefix import YouTube
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit
app.config['DOWNLOAD_FOLDER'] = Path('downloads')
app.config['DOWNLOAD_FOLDER'].mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_youtube_url(url):
    """Validate YouTube URL format."""
    youtube_regex = (
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    match = re.match(youtube_regex, url)
    if not match:
        raise ValueError("Invalid YouTube URL format")
    return url

def sanitize_filename(filename):
    """Sanitize filename for safe storage."""
    filename = secure_filename(filename)
    filename = re.sub(r'\s+', '_', filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base, ext = os.path.splitext(filename)
    if not ext:
        ext = '.mp3'
    return f"{base}_{timestamp}{ext}"[:255]

def get_video_info(url):
    """Get video information without downloading."""
    try:
        yt = YouTube(url)
        return {
            'title': yt.title,
            'author': yt.author,
            'length': yt.length,
            'thumbnail_url': yt.thumbnail_url
        }
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        raise

def download_audio(url):
    """Download audio synchronously."""
    try:
        yt = YouTube(url)
        audio_stream = yt.streams.get_audio_only()
        filename = sanitize_filename(f"{yt.title}.mp3")
        file_path = app.config['DOWNLOAD_FOLDER'] / filename
        
        audio_stream.download(
            output_path=str(app.config['DOWNLOAD_FOLDER']),
            filename=filename
        )
        
        return str(file_path)
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/video-info', methods=['POST'])
def get_info():
    try:
        url = request.json.get('url')
        validate_youtube_url(url)
        video_info = get_video_info(url)
        return jsonify({'success': True, 'data': video_info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/download', methods=['POST'])
def download():
    try:
        url = request.json.get('url')
        validate_youtube_url(url)
        file_path = download_audio(url)
        
        return jsonify({
            'success': True,
            'download_url': f'/download/{os.path.basename(file_path)}'
        })
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/download/<filename>')
def serve_file(filename):
    try:
        return send_file(
            app.config['DOWNLOAD_FOLDER'] / filename,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 404

@app.errorhandler(413)
def too_large(e):
    return jsonify({'success': False, 'error': 'File too large'}), 413

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error_message="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error_message="Internal server error"), 500

if __name__ == '__main__':
    app.run(debug=True)