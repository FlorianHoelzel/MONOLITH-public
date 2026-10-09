import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit


JPEG_START = b"\xff\xd8"
JPEG_END = b"\xff\xd9"
MAX_FRAME_BUFFER_BYTES = 12 * 1024 * 1024


class CameraStreamUnavailable(RuntimeError):
    pass


class CameraStreamBusy(RuntimeError):
    pass


@dataclass(frozen=True)
class CameraPreviewConfig:
    rtsp_url: str
    ffmpeg_path: str
    fps: int
    width: int
    quality: int


def _environment_integer(
    name,
    default,
    minimum,
    maximum,
):
    try:
        value = int(
            os.getenv(name, str(default))
        )
    except (TypeError, ValueError):
        value = default

    return max(
        minimum,
        min(value, maximum),
    )


def _authenticated_rtsp_url(
    url,
    username,
    password,
):
    parts = urlsplit(url)

    if parts.scheme not in {"rtsp", "rtsps"}:
        return ""

    if not parts.hostname:
        return ""

    if not username and not password:
        return url

    hostname = parts.hostname

    if ":" in hostname:
        hostname = f"[{hostname}]"

    if parts.port:
        hostname = f"{hostname}:{parts.port}"

    credentials = quote(
        username,
        safe="",
    )

    if password:
        credentials += ":" + quote(
            password,
            safe="",
        )

    return urlunsplit((
        parts.scheme,
        f"{credentials}@{hostname}",
        parts.path,
        parts.query,
        parts.fragment,
    ))


def get_camera_preview_config():
    url = os.getenv(
        "CAMERA_RTSP_URL",
        "",
    ).strip()
    username = os.getenv(
        "CAMERA_RTSP_USERNAME",
        "",
    ).strip()
    password = os.getenv(
        "CAMERA_RTSP_PASSWORD",
        "",
    )
    ffmpeg_path = os.getenv(
        "CAMERA_FFMPEG_PATH",
        "ffmpeg",
    ).strip() or "ffmpeg"

    return CameraPreviewConfig(
        rtsp_url=_authenticated_rtsp_url(
            url,
            username,
            password,
        ),
        ffmpeg_path=ffmpeg_path,
        fps=_environment_integer(
            "CAMERA_PREVIEW_FPS",
            10,
            1,
            15,
        ),
        width=_environment_integer(
            "CAMERA_PREVIEW_WIDTH",
            1280,
            320,
            1920,
        ),
        quality=_environment_integer(
            "CAMERA_PREVIEW_QUALITY",
            5,
            2,
            12,
        ),
    )


def _ffmpeg_available(path):
    if os.path.dirname(path):
        return os.path.isfile(path)

    return shutil.which(path) is not None


def get_camera_stream_status():
    config = get_camera_preview_config()

    if not config.rtsp_url:
        return {
            "live_available": False,
            "live_reason": "not_configured",
        }

    if not _ffmpeg_available(
        config.ffmpeg_path
    ):
        return {
            "live_available": False,
            "live_reason": "ffmpeg_missing",
        }

    return {
        "live_available": True,
        "live_reason": None,
        "preview_fps": config.fps,
    }


def _iter_jpeg_frames(stream):
    buffer = bytearray()

    while True:
        chunk = stream.read(65536)

        if not chunk:
            return

        buffer.extend(chunk)

        while True:
            start = buffer.find(JPEG_START)

            if start < 0:
                if len(buffer) > 1:
                    del buffer[:-1]
                break

            if start:
                del buffer[:start]

            end = buffer.find(
                JPEG_END,
                len(JPEG_START),
            )

            if end < 0:
                if (
                    len(buffer)
                    > MAX_FRAME_BUFFER_BYTES
                ):
                    buffer.clear()
                break

            frame_end = end + len(JPEG_END)
            frame = bytes(buffer[:frame_end])
            del buffer[:frame_end]
            yield frame


def _stop_process(process):
    if process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _ffmpeg_command(config):
    return [
        config.ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-rtsp_transport",
        "tcp",
        "-timeout",
        "5000000",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-analyzeduration",
        "1000000",
        "-probesize",
        "1000000",
        "-i",
        config.rtsp_url,
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        (
            f"fps={config.fps},"
            f"scale={config.width}:-2:"
            "force_original_aspect_ratio=decrease"
        ),
        "-q:v",
        str(config.quality),
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]


def _stream_frames(
    config,
    release_slot,
):
    process = None

    try:
        command = _ffmpeg_command(config)
        startup_info = None
        creation_flags = 0

        if os.name == "nt":
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= (
                subprocess.STARTF_USESHOWWINDOW
            )
            creation_flags = getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            )

        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
            startupinfo=startup_info,
            creationflags=creation_flags,
        )

        if process.stdout is None:
            return

        for frame in _iter_jpeg_frames(
            process.stdout
        ):
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                + (
                    f"Content-Length: {len(frame)}\r\n\r\n"
                ).encode("ascii")
                + frame
                + b"\r\n"
            )
    finally:
        if process is not None:
            if process.stdout is not None:
                process.stdout.close()
            _stop_process(process)

        release_slot()


CAMERA_MAX_VIEWERS = _environment_integer(
    "CAMERA_MAX_VIEWERS",
    2,
    1,
    4,
)
camera_stream_slots = threading.BoundedSemaphore(
    CAMERA_MAX_VIEWERS
)


def open_camera_stream():
    status = get_camera_stream_status()

    if not status["live_available"]:
        raise CameraStreamUnavailable(
            status["live_reason"]
        )

    if not camera_stream_slots.acquire(
        blocking=False
    ):
        raise CameraStreamBusy()

    config = get_camera_preview_config()

    return _stream_frames(
        config,
        camera_stream_slots.release,
    )
