from flask import Flask, request, jsonify
import base64
import subprocess
import tempfile
import os

app = Flask(__name__)


@app.route('/convert', methods=['POST'])
def convert():
    # Get base64 input
    data = request.json
    if not data or 'ogg_data' not in data:
        return jsonify({"error": "Missing ogg_data field"}), 400

    try:
        # Create temp files
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as ogg_file, \
                tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:

            # Decode and write OGG
            ogg_bytes = base64.b64decode(data['ogg_data'])
            ogg_file.write(ogg_bytes)
            ogg_file.flush()

            # Convert using FFmpeg
            subprocess.run([
                'ffmpeg', '-y',
                '-i', ogg_file.name,
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                wav_file.name
            ], check=True, capture_output=True)

            # Read and encode WAV
            with open(wav_file.name, 'rb') as f:
                wav_b64 = base64.b64encode(f.read()).decode('utf-8')

        # Cleanup
        os.unlink(ogg_file.name)
        os.unlink(wav_file.name)

        return jsonify({"wav_data": wav_b64})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)