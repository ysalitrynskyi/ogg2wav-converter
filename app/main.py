"""OGG -> WAV converter microservice.

A small Flask HTTP API that decodes a base64-encoded OGG payload, transcodes it
to WAV with FFmpeg, and returns the result base64-encoded.

Backward compatibility contract (v1.x):
    POST /convert  {"ogg_data": "<base64>"}  ->  {"wav_data": "<base64>"}
By default the output is 16 kHz, mono, signed 16-bit PCM WAV -- identical to the
original v1.0 service. New optional fields and endpoints are purely additive.
"""

import base64
import binascii
import logging
import os
import subprocess
import tempfile

from flask import Flask, jsonify, request

__version__ = "1.1.0"

app = Flask(__name__)

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("ogg2wav")


def _int_env(name, default):
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


# Configuration (env-overridable). Defaults keep the original v1.0 behavior.
MAX_CONTENT_LENGTH = _int_env("MAX_CONTENT_LENGTH", 100 * 1024 * 1024)  # 100 MB
FFMPEG_TIMEOUT = _int_env("FFMPEG_TIMEOUT", 60)  # seconds
PORT = _int_env("PORT", 5000)

app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Conversion defaults -- MUST match the original v1.0 service exactly.
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
OUTPUT_CODEC = "pcm_s16le"

# Allowlists keep user-supplied options from turning into arbitrary FFmpeg args.
ALLOWED_SAMPLE_RATES = {8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000}
ALLOWED_CHANNELS = {1, 2}


@app.route("/", methods=["GET"])
def index():
    """Service metadata / discovery endpoint."""
    return jsonify({
        "service": "ogg2wav-converter",
        "version": __version__,
        "endpoints": {
            "POST /convert": "Convert base64 OGG to base64 WAV",
            "GET /health": "Liveness probe",
        },
        "defaults": {
            "sample_rate": DEFAULT_SAMPLE_RATE,
            "channels": DEFAULT_CHANNELS,
            "codec": OUTPUT_CODEC,
        },
    })


@app.route("/health", methods=["GET"])
def health():
    """Liveness probe used by Docker/orchestrators."""
    return jsonify({"status": "ok", "version": __version__})


@app.route("/convert", methods=["POST"])
def convert():
    data = request.get_json(silent=True)
    if not data or "ogg_data" not in data:
        return jsonify({"error": "Missing ogg_data field"}), 400

    # Optional tuning knobs. Omitting them reproduces the original output exactly.
    try:
        sample_rate = int(data.get("sample_rate", DEFAULT_SAMPLE_RATE))
        channels = int(data.get("channels", DEFAULT_CHANNELS))
    except (TypeError, ValueError):
        return jsonify({"error": "sample_rate and channels must be integers"}), 400

    if sample_rate not in ALLOWED_SAMPLE_RATES:
        return jsonify({
            "error": "Unsupported sample_rate",
            "allowed": sorted(ALLOWED_SAMPLE_RATES),
        }), 400
    if channels not in ALLOWED_CHANNELS:
        return jsonify({"error": "channels must be 1 or 2"}), 400

    # Lenient decode (matches v1.0: tolerates newline-wrapped base64).
    try:
        ogg_bytes = base64.b64decode(data["ogg_data"])
    except (binascii.Error, ValueError):
        return jsonify({"error": "Invalid base64 in ogg_data"}), 400

    if not ogg_bytes:
        return jsonify({"error": "ogg_data is empty"}), 400

    ogg_path = None
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_file:
            ogg_path = ogg_file.name
            ogg_file.write(ogg_bytes)

        wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(wav_fd)

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", ogg_path,
                "-acodec", OUTPUT_CODEC,
                "-ar", str(sample_rate),
                "-ac", str(channels),
                wav_path,
            ],
            check=True,
            capture_output=True,
            timeout=FFMPEG_TIMEOUT,
        )

        with open(wav_path, "rb") as f:
            wav_b64 = base64.b64encode(f.read()).decode("utf-8")

        return jsonify({"wav_data": wav_b64})

    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg timed out after %ss", FFMPEG_TIMEOUT)
        return jsonify({"error": "Conversion timed out"}), 504
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", "replace") if e.stderr else ""
        logger.warning("ffmpeg failed (rc=%s): %s", e.returncode, stderr[:500])
        return jsonify({"error": "Conversion failed: invalid or unsupported OGG data"}), 400
    except Exception:
        logger.exception("Unexpected error during conversion")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        for path in (ogg_path, wav_path):
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    logger.warning("Failed to remove temp file %s", path)


if __name__ == "__main__":
    # Development entry point only. Production uses gunicorn (see Dockerfile).
    app.run(host="0.0.0.0", port=PORT)
