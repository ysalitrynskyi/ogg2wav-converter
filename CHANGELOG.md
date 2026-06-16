# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [1.1.0]

### Added
- `GET /health` liveness endpoint (also wired into the Docker `HEALTHCHECK`).
- `GET /` service metadata / discovery endpoint.
- Optional `sample_rate` and `channels` fields on `POST /convert`. Omitting them
  reproduces the original 16 kHz mono output exactly.
- Production WSGI server (gunicorn) with env-tunable workers/threads/timeout.
- Configurable limits via env: `MAX_CONTENT_LENGTH`, `FFMPEG_TIMEOUT`, `PORT`.
- Test suite, `docker-compose.yml`, `.dockerignore`, MIT `LICENSE`.
- GitHub Actions CI that runs tests and publishes the image to the GitHub
  Container Registry (`ghcr.io/ysalitrynskyi/ogg2wav-converter`).

### Changed
- FFmpeg now runs with a timeout (default 60s) so a malformed input cannot hang
  a worker indefinitely.
- Temp files are always cleaned up (moved into a `finally` block); previously a
  failed conversion leaked files into the temp dir.
- Error responses no longer leak raw exception strings. Invalid input now returns
  `400` (previously some client errors surfaced as `500`).
- Container runs as a non-root user.

### Compatibility
- **Fully backward compatible.** `POST /convert {"ogg_data": "..."}` returns
  `{"wav_data": "..."}` with byte-identical default output. Existing customers can
  pull the new image with no client changes.

## [1.0.0]
- Initial release: `POST /convert` base64 OGG → base64 WAV (16 kHz, mono, PCM s16le).
