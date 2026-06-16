# OGG → WAV Converter Microservice

[![Build and Publish](https://github.com/ysalitrynskyi/ogg2wav-converter/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/ysalitrynskyi/ogg2wav-converter/actions/workflows/docker-publish.yml)
[![Container](https://img.shields.io/badge/ghcr.io-ogg2wav--converter-2496ED?logo=github)](https://github.com/ysalitrynskyi/ogg2wav-converter/pkgs/container/ogg2wav-converter)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)

A tiny, self-contained HTTP microservice that converts **base64-encoded OGG**
audio to **base64-encoded WAV** using [FFmpeg](https://ffmpeg.org/). Ships as a
single Docker image — no local audio tooling required on the client side.

By default the output is **16 kHz, mono, signed 16-bit PCM** — ideal as a
pre-processing step for speech-to-text / ASR pipelines.

---

## Quick start

The image is built by CI and published to the GitHub Container Registry (GHCR):

```bash
docker run -p 5000:5000 ghcr.io/ysalitrynskyi/ogg2wav-converter:latest
```

Convert a file:

```bash
# Encode -> send -> decode the returned WAV
OGG_B64=$(base64 -i input.ogg)
curl -s -X POST http://localhost:5000/convert \
  -H "Content-Type: application/json" \
  -d "{\"ogg_data\": \"$OGG_B64\"}" \
  | python3 -c "import sys,json,base64; open('output.wav','wb').write(base64.b64decode(json.load(sys.stdin)['wav_data']))"
```

Or with Docker Compose:

```bash
docker compose up
```

---

## API

### `POST /convert`

Convert a base64 OGG payload to base64 WAV.

**Request body**

| Field         | Type   | Required | Default | Description                                            |
| ------------- | ------ | -------- | ------- | ------------------------------------------------------ |
| `ogg_data`    | string | yes      | —       | Base64-encoded OGG audio.                              |
| `sample_rate` | int    | no       | `16000` | Output sample rate. One of: 8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000. |
| `channels`    | int    | no       | `1`     | Output channels: `1` (mono) or `2` (stereo).           |

**Response `200`**

```json
{ "wav_data": "<base64-encoded WAV>" }
```

**Errors**

| Status | When                                                        |
| ------ | ----------------------------------------------------------- |
| `400`  | Missing/invalid `ogg_data`, bad params, or undecodable OGG. |
| `413`  | Payload exceeds `MAX_CONTENT_LENGTH`.                       |
| `504`  | Conversion exceeded `FFMPEG_TIMEOUT`.                       |
| `500`  | Unexpected internal error.                                  |

Error bodies have the shape `{ "error": "<message>" }`.

### `GET /health`

Liveness probe. Returns `{ "status": "ok", "version": "..." }`. Also wired into
the image's Docker `HEALTHCHECK`.

### `GET /`

Service metadata: version, endpoints, and default conversion settings.

---

## Example (Python client)

```python
import base64, requests

with open("input.ogg", "rb") as f:
    ogg_b64 = base64.b64encode(f.read()).decode()

resp = requests.post("http://localhost:5000/convert", json={"ogg_data": ogg_b64})
resp.raise_for_status()

with open("output.wav", "wb") as f:
    f.write(base64.b64decode(resp.json()["wav_data"]))
```

---

## Configuration

All settings are environment variables — the defaults reproduce the original
behavior, so nothing needs to be set.

| Variable             | Default     | Description                                       |
| -------------------- | ----------- | ------------------------------------------------- |
| `PORT`               | `5000`      | Port the server binds to.                         |
| `WEB_CONCURRENCY`    | `2`         | Gunicorn worker processes.                        |
| `THREADS`            | `4`         | Threads per worker.                               |
| `GUNICORN_TIMEOUT`   | `120`       | Worker timeout (seconds).                         |
| `FFMPEG_TIMEOUT`     | `60`        | Max seconds for a single conversion before `504`. |
| `MAX_CONTENT_LENGTH` | `104857600` | Max request body in bytes (100 MB).               |
| `LOG_LEVEL`          | `info`      | Log verbosity.                                    |

Example:

```bash
docker run -p 8080:8080 \
  -e PORT=8080 -e WEB_CONCURRENCY=4 -e FFMPEG_TIMEOUT=120 \
  ghcr.io/ysalitrynskyi/ogg2wav-converter:latest
```

---

## Local development

```bash
pip install -r app/requirements.txt
python app/main.py          # dev server on :5000
python -m pytest tests/     # run the test suite
```

> `python app/main.py` uses Flask's development server. The Docker image uses
> gunicorn for production.

---

## Upgrading from 1.0.x

`1.1.0` is **fully backward compatible**. Pull the new image and your existing
`POST /convert {"ogg_data": "..."}` calls return byte-identical default output —
no client changes needed. See [CHANGELOG.md](CHANGELOG.md) for what's new
(health endpoint, optional `sample_rate`/`channels`, gunicorn, hardening).

```bash
docker pull ghcr.io/ysalitrynskyi/ogg2wav-converter:latest
```

---

## How it works

```
client ──base64 OGG──▶ /convert ──▶ FFmpeg (pcm_s16le) ──▶ base64 WAV ──▶ client
```

The service decodes the payload to a temp file, invokes FFmpeg as an argument
list (no shell — no command injection), reads the result back, and always cleans
up its temp files. FFmpeg runs with a timeout and the container runs as a
non-root user.

---

## Container image

Images are built and published automatically by
[GitHub Actions](.github/workflows/docker-publish.yml) to GHCR on every push to
`main` and on version tags.

| Tag                    | Points to                                  |
| ---------------------- | ------------------------------------------ |
| `latest`               | Latest build from `main`.                  |
| `1.1.0`, `1.1`         | Specific release (pushed from `vX.Y.Z` git tags). |
| `main`, `sha-<commit>` | Branch / commit-pinned builds.             |

```bash
docker pull ghcr.io/ysalitrynskyi/ogg2wav-converter:latest
```

Cutting a release:

```bash
git tag v1.1.0 && git push origin v1.1.0   # CI builds and publishes the tag
```

## License

[MIT](LICENSE) © Yevhen Salitrynskyi
