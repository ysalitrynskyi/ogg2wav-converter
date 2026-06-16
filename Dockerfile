FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/ysalitrynskyi/ogg2wav-converter" \
      org.opencontainers.image.description="OGG to WAV converter microservice (Flask + FFmpeg)" \
      org.opencontainers.image.licenses="MIT"

# Install FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

# Run as an unprivileged user instead of root.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health').status==200 else 1)"

# Production server. Override host/port/workers via env (PORT, WEB_CONCURRENCY...).
CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:app"]
