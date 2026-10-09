import asyncio
import ctypes
import hmac
import http.server
import json
import os
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path


try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager,
    )
except ImportError:
    GlobalSystemMediaTransportControlsSessionManager = None


# ============================================================
# CONFIG
# ============================================================

PORT = int(
    os.getenv(
        "PC_AGENT_PORT",
        "8765",
    )
)

MEDIA_REFRESH_SECONDS = max(
    1.0,
    float(
        os.getenv(
            "PC_MEDIA_REFRESH_SECONDS",
            "2",
        )
    ),
)


def load_token():
    token = os.getenv(
        "PC_AGENT_TOKEN",
        "",
    ).strip()

    if token:
        return token

    configured_file = os.getenv(
        "PC_AGENT_TOKEN_FILE",
        "",
    ).strip()
    token_files = []

    if configured_file:
        token_files.append(
            Path(configured_file)
        )

    token_files.extend((
        Path(__file__).with_name(
            "pc-agent-token.txt"
        ),
        Path(
            os.getenv(
                "LOCALAPPDATA",
                Path.home(),
            )
        )
        / "MONOLITH"
        / "pc-agent-token.txt",
    ))

    for token_file in token_files:
        try:
            token = token_file.read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            continue

        if token:
            return token

    return ""


TOKEN = load_token()


# ============================================================
# MEDIA STATUS
# ============================================================

PLAYBACK_STATES = {
    0: "closed",
    1: "opened",
    2: "changing",
    3: "stopped",
    4: "playing",
    5: "paused",
}


def now_iso():
    return datetime.now().astimezone().isoformat(
        timespec="seconds"
    )


def app_display_name(app_id):
    normalized = str(
        app_id or ""
    ).lower()
    known_apps = {
        "chrome": "Google Chrome",
        "firefox": "Firefox",
        "msedge": "Microsoft Edge",
        "netflix": "Netflix",
        "plex": "Plex",
        "spotify": "Spotify",
        "vlc": "VLC",
    }

    for key, label in known_apps.items():
        if key in normalized:
            return label

    if not app_id:
        return None

    base_name = str(app_id).split("!")[0]
    return base_name.rsplit(".", 1)[-1]


def session_playback_state(session):
    try:
        playback_info = (
            session.get_playback_info()
        )
        status = int(
            playback_info.playback_status
        )
    except (AttributeError, TypeError, ValueError):
        return "stopped"

    return PLAYBACK_STATES.get(
        status,
        "stopped",
    )


async def read_windows_media():
    if (
        GlobalSystemMediaTransportControlsSessionManager
        is None
    ):
        return empty_media_status(
            available=False,
            error="Windows-Medienmodul fehlt",
        )

    manager = await (
        GlobalSystemMediaTransportControlsSessionManager
        .request_async()
    )
    sessions = list(
        manager.get_sessions()
    )
    current_session = (
        manager.get_current_session()
    )
    playing_session = next(
        (
            session
            for session in sessions
            if session_playback_state(session)
            == "playing"
        ),
        None,
    )
    session = (
        playing_session
        or current_session
        or (
            sessions[0]
            if sessions
            else None
        )
    )

    if session is None:
        return empty_media_status()

    properties = await (
        session.try_get_media_properties_async()
    )
    playback_state = session_playback_state(
        session
    )
    app_id = getattr(
        session,
        "source_app_user_model_id",
        None,
    )

    return {
        "available": True,
        "session_active": True,
        "playing": playback_state == "playing",
        "playback_state": playback_state,
        "title": getattr(
            properties,
            "title",
            None,
        ) or None,
        "artist": getattr(
            properties,
            "artist",
            None,
        ) or None,
        "album": getattr(
            properties,
            "album_title",
            None,
        ) or None,
        "app": app_id,
        "app_name": app_display_name(app_id),
        "updated_at": now_iso(),
        "error": None,
    }


def empty_media_status(
    available=True,
    error=None,
):
    return {
        "available": available,
        "session_active": False,
        "playing": False,
        "playback_state": "stopped",
        "title": None,
        "artist": None,
        "album": None,
        "app": None,
        "app_name": None,
        "updated_at": now_iso(),
        "error": error,
    }


def media_error_message(error):
    error_code = getattr(
        error,
        "winerror",
        None,
    )

    if error_code in (
        -2147023836,
        0x80070424,
    ):
        return (
            "Windows-Medienstatus benötigt eine "
            "interaktive Benutzer-Sitzung"
        )

    error_name = type(error).__name__
    error_text = str(error).strip()

    if error_text:
        return (
            "Windows-Medienstatus konnte nicht "
            f"gelesen werden: {error_name}: "
            f"{error_text[:240]}"
        )

    return (
        "Windows-Medienstatus konnte nicht "
        f"gelesen werden: {error_name}"
    )


class MediaMonitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.status = empty_media_status(
            available=(
                GlobalSystemMediaTransportControlsSessionManager
                is not None
            )
        )
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="pc-media-monitor",
        )

    def start(self):
        self.thread.start()

    def snapshot(self):
        with self.lock:
            return dict(self.status)

    def _run(self):
        while not self.stop_event.is_set():
            try:
                status = asyncio.run(
                    read_windows_media()
                )
            except Exception as error:
                status = empty_media_status(
                    available=False,
                    error=media_error_message(
                        error
                    ),
                )

            with self.lock:
                self.status = status

            self.stop_event.wait(
                MEDIA_REFRESH_SECONDS
            )


media_monitor = MediaMonitor()


# ============================================================
# PC ACTIONS
# ============================================================

def delayed_action(function):
    def worker():
        time.sleep(0.5)
        function()

    threading.Thread(
        target=worker,
        daemon=True,
    ).start()


def shutdown_pc():
    subprocess.run([
        "shutdown",
        "/s",
        "/f",
        "/t",
        "0",
    ])


def restart_pc():
    subprocess.run([
        "shutdown",
        "/r",
        "/f",
        "/t",
        "0",
    ])


def sleep_pc():
    ctypes.windll.powrprof.SetSuspendState(
        False,
        True,
        False,
    )


def lock_pc():
    ctypes.windll.user32.LockWorkStation()


def launch_steam():
    os.startfile(
        "steam://open/bigpicture"
    )


def launch_spotify():
    os.startfile("spotify:")


def launch_browser():
    webbrowser.open(
        "https://www.google.com"
    )


# ============================================================
# HTTP SERVER
# ============================================================

class PCRequestHandler(
    http.server.BaseHTTPRequestHandler
):
    def log_message(
        self,
        _format_string,
        *_args,
    ):
        return

    def authorized(self):
        supplied_token = self.headers.get(
            "X-PC-Token",
            "",
        )

        return bool(TOKEN) and hmac.compare_digest(
            supplied_token,
            TOKEN,
        )

    def send_body(
        self,
        status,
        data,
        content_type,
    ):
        self.send_response(status)
        self.send_header(
            "Content-Type",
            content_type,
        )
        self.send_header(
            "Content-Length",
            str(len(data)),
        )
        self.send_header(
            "Cache-Control",
            "no-store",
        )
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, status, text):
        self.send_body(
            status,
            text.encode("utf-8"),
            "text/plain; charset=utf-8",
        )

    def send_json(self, status, payload):
        self.send_body(
            status,
            json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def do_GET(self):
        if not self.authorized():
            self.send_text(403, "Forbidden")
            return

        if self.path == "/status":
            self.send_text(200, "online")
            return

        if self.path == "/media":
            self.send_json(
                200,
                media_monitor.snapshot(),
            )
            return

        self.send_text(404, "Not found")

    def do_POST(self):
        if not self.authorized():
            self.send_text(403, "Forbidden")
            return

        actions = {
            "/shutdown": (
                "shutdown",
                lambda: delayed_action(
                    shutdown_pc
                ),
            ),
            "/restart": (
                "restart",
                lambda: delayed_action(
                    restart_pc
                ),
            ),
            "/sleep": (
                "sleep",
                lambda: delayed_action(
                    sleep_pc
                ),
            ),
            "/lock": (
                "lock",
                lambda: delayed_action(
                    lock_pc
                ),
            ),
            "/launch/steam": (
                "steam",
                launch_steam,
            ),
            "/launch/spotify": (
                "spotify",
                launch_spotify,
            ),
            "/launch/browser": (
                "browser",
                launch_browser,
            ),
        }
        action = actions.get(self.path)

        if action is None:
            self.send_text(404, "Not found")
            return

        response_text, callback = action
        self.send_text(200, response_text)
        callback()


def main():
    if not TOKEN:
        raise RuntimeError(
            "PC_AGENT_TOKEN oder Token-Datei fehlt"
        )

    media_monitor.start()
    server = http.server.ThreadingHTTPServer(
        ("0.0.0.0", PORT),
        PCRequestHandler,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        media_monitor.stop_event.set()
        server.server_close()


if __name__ == "__main__":
    main()
