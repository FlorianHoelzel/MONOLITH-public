import json
import os
import socket
import threading
import urllib.error
import urllib.request

from dotenv import load_dotenv
from fritzconnection.lib.fritzhosts import FritzHosts


# =============================================================
# ENVIRONMENT
# =============================================================

load_dotenv()


FRITZBOX_ADDRESS = os.getenv(
    "FRITZBOX_ADDRESS"
)

FRITZBOX_USER = os.getenv(
    "FRITZBOX_USER"
)

FRITZBOX_PASSWORD = os.getenv(
    "FRITZBOX_PASSWORD"
)

PC_MAC = (
    os.getenv(
        "PC_MAC",
        "",
    )
    .strip()
    .replace(
        "-",
        ":",
    )
    .upper()
)

PC_IP = os.getenv(
    "PC_IP",
    "",
).strip()

PC_AGENT_TOKEN = os.getenv(
    "PC_AGENT_TOKEN",
    "",
).strip()

try:
    PC_AGENT_PORT = int(
        os.getenv(
            "PC_AGENT_PORT",
            "8765",
        )
    )
except ValueError:
    PC_AGENT_PORT = 8765

try:
    PC_AGENT_TIMEOUT_SECONDS = max(
        0.2,
        float(
            os.getenv(
                "PC_AGENT_TIMEOUT_SECONDS",
                "2",
            )
        ),
    )
except ValueError:
    PC_AGENT_TIMEOUT_SECONDS = 2.0


try:
    CHECK_INTERVAL_SECONDS = max(
        2,
        int(
            os.getenv(
                "PC_CHECK_INTERVAL_SECONDS",
                "5",
            )
        ),
    )

except ValueError:
    CHECK_INTERVAL_SECONDS = 5


# =============================================================
# PC STATUS MONITOR
# =============================================================

class PcStatusMonitor:
    def __init__(
        self,
        on_status,
        on_media_status=None,
    ):
        self.on_status = on_status
        self.on_media_status = on_media_status
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.fritz_hosts = None


    def connect_fritzbox(self):
        if (
            not FRITZBOX_ADDRESS
            or not FRITZBOX_USER
            or not FRITZBOX_PASSWORD
        ):
            print(
                "[PC ERROR] "
                "FRITZ!Box Zugangsdaten fehlen"
            )

            return False


        try:
            self.fritz_hosts = (
                FritzHosts(
                    address=
                        FRITZBOX_ADDRESS,

                    user=
                        FRITZBOX_USER,

                    password=
                        FRITZBOX_PASSWORD,
                )
            )

            return True


        except Exception as error:
            print(
                "[PC ERROR] "
                "FRITZ!Box Verbindung fehlgeschlagen: "
                f"{error}"
            )

            self.fritz_hosts = None

            return False


    def read_status(self):
        if PC_IP and PC_AGENT_PORT > 0:
            try:
                with socket.create_connection(
                    (PC_IP, PC_AGENT_PORT),
                    timeout=PC_AGENT_TIMEOUT_SECONDS,
                ):
                    return True
            except OSError:
                return False

        if not PC_MAC:
            return None

        if (
            self.fritz_hosts
            is None
        ):
            if not self.connect_fritzbox():
                return None

        try:
            return bool(
                self.fritz_hosts
                .get_host_status(
                    PC_MAC
                )
            )

        except Exception as error:
            print(
                "[PC ERROR] "
                "Statusabfrage fehlgeschlagen: "
                f"{error}"
            )

            self.fritz_hosts = None

            return None


    def read_media_status(self):
        if (
            not PC_IP
            or PC_AGENT_PORT <= 0
            or not PC_AGENT_TOKEN
        ):
            return None

        request = urllib.request.Request(
            (
                f"http://{PC_IP}:"
                f"{PC_AGENT_PORT}/media"
            ),
            headers={
                "X-PC-Token": PC_AGENT_TOKEN,
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=PC_AGENT_TIMEOUT_SECONDS,
            ) as response:
                payload = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )
        except (
            OSError,
            ValueError,
            urllib.error.HTTPError,
        ):
            return {
                "available": False,
                "session_active": False,
                "playing": False,
                "playback_state": "stopped",
                "error": (
                    "PC-Medienstatus nicht verfügbar"
                ),
            }

        if not isinstance(payload, dict):
            return None

        return payload


    def monitor_loop(self):
        while self.running:
            status = self.read_status()


            if status is not None:
                self.on_status(
                    status
                )

            if self.on_media_status is not None:
                media_status = (
                    self.read_media_status()
                    if status
                    else {
                        "available": False,
                        "session_active": False,
                        "playing": False,
                        "playback_state": "stopped",
                        "error": "PC ist offline",
                    }
                )

                if media_status is not None:
                    self.on_media_status(
                        media_status
                    )


            self.stop_event.wait(
                CHECK_INTERVAL_SECONDS
            )


    def start(self):
        if self.running:
            return


        if not PC_MAC:
            print(
                "[PC ERROR] "
                "PC_MAC fehlt; Statusmonitor nicht gestartet"
            )

            return


        self.running = True
        self.stop_event.clear()


        self.thread = (
            threading.Thread(
                target=
                    self.monitor_loop,

                daemon=
                    True,

                name=
                    "MONOLITH-PC-Status",
            )
        )


        self.thread.start()


        print(
            "[PC] "
            "Read-only Statusmonitor gestartet"
        )


pc_status_monitor = None


def start_pc_status_monitor(
    on_status,
    on_media_status=None,
):
    global pc_status_monitor


    if pc_status_monitor is None:
        pc_status_monitor = (
            PcStatusMonitor(
                on_status,
                on_media_status,
            )
        )


    pc_status_monitor.start()
