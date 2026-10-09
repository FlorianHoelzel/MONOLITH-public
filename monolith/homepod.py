import asyncio
import os
import threading
from contextlib import suppress
from datetime import datetime

import pyatv
from dotenv import load_dotenv
from pyatv.const import (
    DeviceModel,
    DeviceState,
)


load_dotenv()


HOMEPOD_IP = os.getenv(
    "HOMEPOD_IP",
    "",
).strip()

HOMEPOD_IDENTIFIER = os.getenv(
    "HOMEPOD_IDENTIFIER",
    "",
).strip().upper()

HOMEPOD_NAME = os.getenv(
    "HOMEPOD_NAME",
    "",
).strip()

HOMEPOD_SCAN_INTERVAL_SECONDS = max(
    2,
    int(
        os.getenv(
            "HOMEPOD_SCAN_INTERVAL_SECONDS",
            "2",
        )
    ),
)

HOMEPOD_SCAN_TIMEOUT_SECONDS = max(
    1,
    int(
        os.getenv(
            "HOMEPOD_SCAN_TIMEOUT_SECONDS",
            "1",
        )
    ),
)


HOMEPOD_MODELS = {
    DeviceModel.HomePod,
    DeviceModel.HomePodMini,
    DeviceModel.HomePodGen2,
}


class HomePodMonitor:
    def __init__(
        self,
        on_status,
    ):
        self.on_status = on_status
        self.thread = None
        self.stop_event = threading.Event()
        self.loop = None
        self.last_connected = None

    def start(self):
        if (
            self.thread
            and self.thread.is_alive()
        ):
            return

        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._run,
            name="MONOLITH-HomePod",
            daemon=True,
        )
        self.thread.start()

        print(
            "[HOMEPOD] "
            f"pyatv-Monitor für {HOMEPOD_IP} gestartet"
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
            try:
                config = await self._find_homepod()

                if config is None:
                    self._publish_unavailable()
                else:
                    await self._publish_config(config)

            except Exception as error:
                self._publish_unavailable(
                    error=str(error),
                )

            if not self.stop_event.is_set():
                await asyncio.sleep(
                    HOMEPOD_SCAN_INTERVAL_SECONDS
                )

    async def _find_homepod(self):
        if not (HOMEPOD_IP or HOMEPOD_IDENTIFIER):
            return None

        hosts = (
            [HOMEPOD_IP]
            if HOMEPOD_IP
            else None
        )

        configs = await pyatv.scan(
            self.loop,
            timeout=HOMEPOD_SCAN_TIMEOUT_SECONDS,
            hosts=hosts,
        )

        for config in configs:
            identifier = (
                config.identifier or ""
            ).upper()

            if (
                HOMEPOD_IDENTIFIER
                and identifier
                == HOMEPOD_IDENTIFIER
            ):
                return config

        for config in configs:
            if (
                config.device_info.model
                in HOMEPOD_MODELS
                and (
                    not HOMEPOD_NAME
                    or config.name.casefold()
                    == HOMEPOD_NAME.casefold()
                )
            ):
                return config

        return None

    async def _publish_config(
        self,
        config,
    ):
        device_info = config.device_info
        model = self._model_name(
            device_info.model
        )
        version = (
            device_info.version
            or None
        )
        playback = await self._get_playback(
            config
        )
        if playback is None:
            self._publish_unavailable(error="Wiedergabestatus nicht abrufbar")
            return

        self.on_status({
            "value": (
                "Playing"
                if playback["playing"]
                else "Paused"
            ),
            "connected": True,
            "playing": playback["playing"],
            "playback_state": playback[
                "playback_state"
            ],
            "title": playback["title"],
            "artist": playback["artist"],
            "artwork": playback["artwork"],
            "address": str(config.address),
            "identifier": config.identifier,
            "model": model,
            "operating_system": str(
                device_info.operating_system.name
            ),
            "version": version,
            "last_seen": self._now_iso(),
            "error": None,
        })

        if self.last_connected is not True:
            details = (
                f"{model} · {version}"
                if version
                else model
            )
            print(
                "[HOMEPOD] "
                f"{config.name} erreichbar "
                f"({config.address}) · {details}"
            )

        self.last_connected = True

    async def _get_playback(
        self,
        config,
    ):
        apple_tv = None

        try:
            apple_tv = await pyatv.connect(
                config,
                self.loop,
            )
            playing = await apple_tv.metadata.playing()
            active = playing.device_state in {
                DeviceState.Loading,
                DeviceState.Playing,
                DeviceState.Seeking,
            }
            artwork = None

            if active:
                with suppress(Exception):
                    artwork_info = await (
                        apple_tv.metadata.artwork(
                            width=512
                        )
                    )

                    if artwork_info:
                        artwork = {
                            "bytes": artwork_info.bytes,
                            "mimetype": artwork_info.mimetype,
                        }

            return {
                "playing": active,
                "playback_state": (
                    playing.device_state.name.lower()
                ),
                "title": (
                    playing.title
                    if active
                    else None
                ),
                "artist": (
                    playing.artist
                    if active
                    else None
                ),
                "artwork": artwork,
            }

        except Exception:
            return None

        finally:
            if apple_tv is not None:
                with suppress(Exception):
                    pending = apple_tv.close()

                    if pending:
                        await asyncio.gather(
                            *pending,
                            return_exceptions=True,
                        )

    def _publish_unavailable(
        self,
        error=None,
    ):
        self.on_status({
            "value": "Unbekannt",
            "connected": False,
            "playing": False,
            "playback_state": "unknown",
            "title": None,
            "artist": None,
            "artwork": None,
            "address": HOMEPOD_IP or None,
            "last_seen": None,
            "error": error,
        })

        if self.last_connected is not False:
            message = (
                f": {error}"
                if error
                else ""
            )
            print(
                "[HOMEPOD] "
                "HomePod nicht erreichbar"
                f"{message}"
            )

        self.last_connected = False

    @staticmethod
    def _model_name(model):
        names = {
            DeviceModel.HomePod: "HomePod",
            DeviceModel.HomePodMini: "HomePod mini",
            DeviceModel.HomePodGen2: "HomePod (2. Gen.)",
        }

        return names.get(
            model,
            model.name,
        )

    @staticmethod
    def _now_iso():
        return datetime.now().astimezone().isoformat(
            timespec="seconds"
        )


homepod_monitor = None


def start_homepod_monitor(
    on_status,
):
    global homepod_monitor

    if homepod_monitor is None:
        homepod_monitor = HomePodMonitor(
            on_status
        )

    homepod_monitor.start()


def stop_homepod_monitor():
    if homepod_monitor is not None:
        with suppress(Exception):
            homepod_monitor.stop()
