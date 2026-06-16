"""Gunicorn configuration for the ogg2wav-converter service.

All values are environment-overridable so the same image can be tuned per
deployment without rebuilding.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("THREADS", "4"))
# Keep above FFMPEG_TIMEOUT (default 60s) so a slow conversion is not killed
# by the worker timeout before the app can return a clean 504.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()
