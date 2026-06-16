"""Unit tests for the ogg2wav-converter service.

Uses only the standard library (unittest + mock). FFmpeg is mocked, so the suite
runs anywhere without audio tooling. A real end-to-end conversion is exercised
separately in the Docker smoke test.
"""

import base64
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import main  # noqa: E402


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


class ServiceTests(unittest.TestCase):
    def setUp(self):
        main.app.testing = True
        self.client = main.app.test_client()

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "ok")

    def test_index(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["service"], "ogg2wav-converter")

    def test_missing_field(self):
        r = self.client.post("/convert", json={})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error"], "Missing ogg_data field")

    def test_bad_base64(self):
        r = self.client.post("/convert", json={"ogg_data": "@@@not-base64@@@"})
        self.assertEqual(r.status_code, 400)

    def test_empty_payload(self):
        r = self.client.post("/convert", json={"ogg_data": ""})
        self.assertEqual(r.status_code, 400)

    def test_bad_sample_rate(self):
        r = self.client.post("/convert", json={"ogg_data": b64(b"x"), "sample_rate": 12345})
        self.assertEqual(r.status_code, 400)

    def test_bad_channels(self):
        r = self.client.post("/convert", json={"ogg_data": b64(b"x"), "channels": 5})
        self.assertEqual(r.status_code, 400)

    @mock.patch("main.subprocess.run")
    def test_success_default(self, mock_run):
        def fake_ffmpeg(cmd, **kwargs):
            with open(cmd[-1], "wb") as f:  # last arg is the output path
                f.write(b"RIFF....WAVEfake")
            return mock.Mock(returncode=0)

        mock_run.side_effect = fake_ffmpeg
        r = self.client.post("/convert", json={"ogg_data": b64(b"OggS-fake-bytes")})

        self.assertEqual(r.status_code, 200)
        self.assertEqual(base64.b64decode(r.get_json()["wav_data"]), b"RIFF....WAVEfake")
        # Defaults must reproduce the original v1.0 ffmpeg invocation.
        args = mock_run.call_args.args[0]
        self.assertIn("16000", args)
        self.assertEqual(args[args.index("-ac") + 1], "1")
        self.assertEqual(args[args.index("-acodec") + 1], "pcm_s16le")

    @mock.patch("main.subprocess.run")
    def test_success_custom_params(self, mock_run):
        def fake_ffmpeg(cmd, **kwargs):
            with open(cmd[-1], "wb") as f:
                f.write(b"wav")
            return mock.Mock(returncode=0)

        mock_run.side_effect = fake_ffmpeg
        r = self.client.post(
            "/convert",
            json={"ogg_data": b64(b"OggS"), "sample_rate": 44100, "channels": 2},
        )
        self.assertEqual(r.status_code, 200)
        args = mock_run.call_args.args[0]
        self.assertIn("44100", args)
        self.assertEqual(args[args.index("-ac") + 1], "2")

    @mock.patch("main.subprocess.run")
    def test_ffmpeg_failure_is_400(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, "ffmpeg", stderr=b"boom")
        r = self.client.post("/convert", json={"ogg_data": b64(b"not-really-ogg")})
        self.assertEqual(r.status_code, 400)

    @mock.patch("main.subprocess.run")
    def test_timeout_is_504(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 60)
        r = self.client.post("/convert", json={"ogg_data": b64(b"OggS")})
        self.assertEqual(r.status_code, 504)

    @mock.patch("main.subprocess.run")
    def test_tempfiles_cleaned_up(self, mock_run):
        import glob
        import tempfile

        def fake_ffmpeg(cmd, **kwargs):
            with open(cmd[-1], "wb") as f:
                f.write(b"wav")
            return mock.Mock(returncode=0)

        mock_run.side_effect = fake_ffmpeg
        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "*.ogg")))
        self.client.post("/convert", json={"ogg_data": b64(b"OggS")})
        after = set(glob.glob(os.path.join(tempfile.gettempdir(), "*.ogg")))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
