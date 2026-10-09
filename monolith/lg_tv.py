import asyncio
import json
import os
import socket
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import suppress
from pathlib import Path

from aiowebostv import WebOsClient
from aiowebostv.webos_client import (
    MAIN_WS_MAX_MSG_SIZE,
    WSS_PORT,
)
from dotenv import load_dotenv

from monolith.data_paths import data_path

load_dotenv()


LG_TV_IP = os.getenv(
    "LG_TV_IP",
    "",
).strip()

LG_TV_MAC = (
    os.getenv(
        "LG_TV_MAC",
        "",
    )
    .strip()
    .replace("-", ":")
    .upper()
)

LG_TV_KEY_FILE = os.getenv(
    "LG_TV_KEY_FILE",
    str(data_path("lg_tv_pairing.json")),
).strip()


APP_NAMES = {
    "com.webos.app.home": "Startseite",
    "com.webos.app.hdmi1": "HDMI 1",
    "com.webos.app.hdmi2": "HDMI 2",
    "com.webos.app.hdmi3": "HDMI 3",
    "com.webos.app.hdmi4": "HDMI 4",
    "com.webos.app.livetv": "Live TV",
    "com.webos.app.settings": "Einstellungen",
}


class LgWebOsClient(WebOsClient):
    async def _create_main_ws(self):
        return await self._ws_connect(
            (
                f"wss://{self.host}:"
                f"{WSS_PORT}"
            ),
            MAIN_WS_MAX_MSG_SIZE,
        )


class LgTvMonitor:
    def __init__(
        self,
        on_status,
    ):
        self.on_status = on_status
        self.thread = None
        self.stop_event = threading.Event()
        self.loop = None
        self.client = None
        self.connected = False
        self.has_connected = False
        self.last_power_value = "Unbekannt"
        self.retry_delay_seconds = 15
        self.last_connection_log = None

    def start(self):
        if (
            self.thread
            and self.thread.is_alive()
        ):
            return

        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._run,
            name="MONOLITH-LG-TV",
            daemon=True,
        )
        self.thread.start()

        print(
            "[LG TV] "
            f"webOS-Monitor für {LG_TV_IP} gestartet"
        )

    def stop(self):
        self.stop_event.set()

        if (
            self.loop
            and self.loop.is_running()
        ):
            self.loop.call_soon_threadsafe(
                lambda: None
            )

    def _run(self):
        asyncio.run(
            self._monitor_forever()
        )

    async def _monitor_forever(self):
        self.loop = asyncio.get_running_loop()

        while not self.stop_event.is_set():
            client = None

            try:
                client_key = (
                    self._read_client_key()
                )

                if not client_key:
                    self.on_status({
                        "value": "Unbekannt",
                        "connected": False,
                        "power_state": (
                            "Kopplung erforderlich"
                        ),
                        "app": None,
                        "app_name": None,
                        "volume": None,
                        "muted": None,
                    })
                    await asyncio.sleep(15)
                    continue

                client = LgWebOsClient(
                    LG_TV_IP,
                    client_key=client_key,
                    connect_timeout=5,
                    heartbeat=5,
                )

                self.client = client

                await client.register_state_update_callback(
                    self._publish_client_state
                )

                await client.connect()

                self._write_client_key(
                    client.client_key
                )

                self.connected = True
                self.has_connected = True
                self.retry_delay_seconds = 15
                self.last_connection_log = None

                await self._publish_client_state()

                await client.connect_task

            except Exception as error:
                self.connected = False

                error_text = str(error)
                is_standby_response = (
                    "1008" in error_text
                    or "Try Again Later"
                    in error_text
                )

                if is_standby_response:
                    self.retry_delay_seconds = 30
                else:
                    self.retry_delay_seconds = 15

                if (
                    is_standby_response
                    and client_key
                ):
                    value = False
                    self.last_power_value = False
                    power_state = "Standby"

                elif self.has_connected:
                    # A dropped webOS socket is not a power-off signal.
                    # Keep the last confirmed value until webOS explicitly
                    # reports standby or a connected state update says off.
                    value = self.last_power_value
                    power_state = (
                        "Nicht erreichbar"
                    )

                else:
                    value = "Unbekannt"
                    power_state = (
                        "Nicht erreichbar"
                    )

                self.on_status({
                    "value": value,
                    "connected": False,
                    "power_state": power_state,
                    "app": None,
                    "app_name": None,
                    "volume": None,
                    "muted": None,
                })

                if is_standby_response:
                    self._log_connection_issue(
                        "standby",
                        "TV ist aus oder im Netzwerk-Standby "
                        "· neuer Versuch in 30 Sekunden",
                    )
                else:
                    self._log_connection_issue(
                        f"error:{type(error).__name__}",
                        "Verbindung nicht verfügbar: "
                        f"{error}",
                    )

            finally:
                self.connected = False

                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()

                self.client = None

            if not self.stop_event.is_set():
                await asyncio.sleep(
                    self.retry_delay_seconds
                )

    def _log_connection_issue(
        self,
        key,
        message,
    ):
        if key == self.last_connection_log:
            return

        self.last_connection_log = key

        print(
            "[LG TV] "
            f"{message}"
        )

    async def _publish_client_state(
        self,
        _state=None,
    ):
        client = self.client

        if (
            client is None
            or not self.connected
        ):
            return

        state = client.tv_state

        power_state = (
            state.power_state.get("state")
            if state.power_state
            else None
        )

        app_id = state.current_app_id
        app_name = APP_NAMES.get(app_id)

        if (
            app_name is None
            and app_id
        ):
            app = state.apps.get(
                app_id,
                {},
            )
            app_name = (
                app.get("title")
                or app.get("name")
                or app_id
            )

        value = state.is_on
        self.last_power_value = value

        self.on_status({
            "value": value,
            "connected": True,
            "power_state": (
                power_state
                or "Unknown"
            ),
            "app": app_id,
            "app_name": app_name,
            "volume": state.volume,
            "muted": state.muted,
        })

    @staticmethod
    def _read_client_key():
        key_path = Path(
            LG_TV_KEY_FILE
        )

        if not key_path.exists():
            return None

        try:
            data = json.loads(
                key_path.read_text(
                    encoding="utf-8"
                )
            )
            return data.get(
                "client_key"
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return None

    @staticmethod
    def _write_client_key(
        client_key,
    ):
        if not client_key:
            return

        key_path = Path(
            LG_TV_KEY_FILE
        )
        key_path.write_text(
            json.dumps(
                {
                    "client_key": client_key,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def set_power(
        self,
        enabled,
    ):
        enabled = bool(enabled)

        if enabled and not self.connected:
            self._send_wake_on_lan()

            return {
                "success": True,
                "action": "wake",
            }

        if (
            not self.connected
            or self.client is None
            or self.loop is None
        ):
            if not enabled:
                return {
                    "success": True,
                    "action": "already_off",
                }

            raise RuntimeError(
                "LG TV ist nicht verbunden"
            )

        command = (
            self.client.power_on()
            if enabled
            else self.client.power_off()
        )

        future = asyncio.run_coroutine_threadsafe(
            command,
            self.loop,
        )

        try:
            future.result(
                timeout=10
            )
        except FutureTimeoutError as error:
            future.cancel()
            raise RuntimeError(
                "LG TV antwortet nicht"
            ) from error

        return {
            "success": True,
            "action": (
                "power_on"
                if enabled
                else "power_off"
            ),
        }

    @staticmethod
    def _send_wake_on_lan():
        mac = LG_TV_MAC.replace(
            ":",
            "",
        )

        if len(mac) != 12:
            raise RuntimeError(
                "LG_TV_MAC ist ungültig"
            )

        magic_packet = (
            b"\xff" * 6
            + bytes.fromhex(mac) * 16
        )

        with socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        ) as wake_socket:
            wake_socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_BROADCAST,
                1,
            )
            wake_socket.sendto(
                magic_packet,
                ("255.255.255.255", 9),
            )


lg_tv_monitor = None


def start_lg_tv_monitor(
    on_status,
):
    global lg_tv_monitor

    if lg_tv_monitor is None:
        lg_tv_monitor = LgTvMonitor(
            on_status
        )

    lg_tv_monitor.start()


def set_lg_tv_power(
    enabled,
):
    if lg_tv_monitor is None:
        raise RuntimeError(
            "LG-TV-Monitor ist nicht gestartet"
        )

    return lg_tv_monitor.set_power(
        enabled
    )


def stop_lg_tv_monitor():
    if lg_tv_monitor is not None:
        with suppress(Exception):
            lg_tv_monitor.stop()
