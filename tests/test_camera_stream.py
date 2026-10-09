import io
import os
import unittest
from unittest.mock import patch

from monolith import camera_stream
from monolith import app as app_module


class CameraStreamTests(unittest.TestCase):
    def test_credentials_are_encoded_into_rtsp_url(self):
        url = camera_stream._authenticated_rtsp_url(
            "rtsp://192.0.2.10:8554/ch2",
            "camera user",
            "p@ss/word",
        )

        self.assertEqual(
            url,
            (
                "rtsp://camera%20user:"
                "p%40ss%2Fword@192.0.2.10:8554/ch2"
            ),
        )

    def test_invalid_scheme_is_not_configured(self):
        with patch.dict(
            os.environ,
            {
                "CAMERA_RTSP_URL": (
                    "http://192.0.2.10/video"
                ),
            },
            clear=False,
        ):
            config = (
                camera_stream
                .get_camera_preview_config()
            )

        self.assertEqual(config.rtsp_url, "")

    def test_preview_defaults_to_ten_fps(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            config = (
                camera_stream
                .get_camera_preview_config()
            )

        self.assertEqual(config.fps, 10)

    def test_status_does_not_expose_connection_details(self):
        with patch.dict(
            os.environ,
            {
                "CAMERA_RTSP_URL": (
                    "rtsp://192.0.2.10:8554/ch2"
                ),
                "CAMERA_RTSP_USERNAME": "viewer",
                "CAMERA_RTSP_PASSWORD": "secret",
            },
            clear=False,
        ), patch(
            "monolith.camera_stream._ffmpeg_available",
            return_value=True,
        ):
            status = (
                camera_stream
                .get_camera_stream_status()
            )

        self.assertTrue(status["live_available"])
        self.assertNotIn("rtsp_url", status)
        self.assertNotIn("username", status)
        self.assertNotIn("password", status)
        self.assertNotIn("secret", repr(status))

    def test_jpeg_frames_are_split_from_pipe(self):
        first = b"\xff\xd8first\xff\xd9"
        second = b"\xff\xd8second\xff\xd9"
        pipe = io.BytesIO(
            b"noise" + first + second
        )

        frames = list(
            camera_stream._iter_jpeg_frames(
                pipe
            )
        )

        self.assertEqual(
            frames,
            [first, second],
        )

    def test_ffmpeg_uses_rtsp_compatible_timeout(self):
        config = camera_stream.CameraPreviewConfig(
            rtsp_url="rtsp://192.0.2.10:8554/ch2",
            ffmpeg_path="ffmpeg",
            fps=10,
            width=1280,
            quality=5,
        )

        command = camera_stream._ffmpeg_command(
            config
        )

        self.assertIn("-timeout", command)
        self.assertNotIn("-rw_timeout", command)
        self.assertLess(
            command.index("-timeout"),
            command.index("-i"),
        )


class CameraStreamApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_live_route_reports_missing_configuration(self):
        with patch.object(
            app_module,
            "open_camera_stream",
            side_effect=(
                camera_stream.CameraStreamUnavailable(
                    "not_configured"
                )
            ),
        ):
            response = self.client.get(
                "/api/camera/live"
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json()["error"],
            "not_configured",
        )

    def test_live_route_streams_without_caching(self):
        chunk = (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            b"\xff\xd8frame\xff\xd9\r\n"
        )

        with patch.object(
            app_module,
            "open_camera_stream",
            return_value=iter([chunk]),
        ):
            response = self.client.get(
                "/api/camera/live"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, chunk)
        self.assertIn(
            "multipart/x-mixed-replace",
            response.content_type,
        )
        self.assertEqual(
            response.headers["Cache-Control"],
            "no-store, private",
        )


if __name__ == "__main__":
    unittest.main()
