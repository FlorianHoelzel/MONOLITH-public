import asyncio
import os
import threading
from contextlib import suppress
from datetime import datetime
from pathlib import Path

import pyatv
from dotenv import load_dotenv
from pyatv.const import (
    DeviceState,
    FeatureName,
    FeatureState,
    PowerState,
    Protocol,
)
from pyatv.settings import MrpTunnel
from pyatv.storage.file_storage import FileStorage

from monolith.data_paths import data_path

load_dotenv()


APPLE_TV_IP = os.getenv(
    "APPLE_TV_IP",
    "",
).strip()

APPLE_TV_IDENTIFIER = os.getenv(
    "APPLE_TV_IDENTIFIER",
    "",
).strip().upper()

APPLE_TV_NAME = os.getenv(
    "APPLE_TV_NAME",
    "",
).strip()

APPLE_TV_STORAGE_FILE = os.getenv(
    "APPLE_TV_STORAGE_FILE",
    str(data_path("apple_tv_pyatv.conf")),
).strip()

APPLE_TV_SCAN_INTERVAL_SECONDS = max(
    2,
    int(
        os.getenv(
            "APPLE_TV_SCAN_INTERVAL_SECONDS",
            "2",
        )
    ),
)

APPLE_TV_SCAN_TIMEOUT_SECONDS = max(
    1,
    int(
        os.getenv(
            "APPLE_TV_SCAN_TIMEOUT_SECONDS",
            "1",
        )
    ),
)


class AppleTvMonitor:
    def __init__(
        self,
        on_status,
    ):
        self.on_status = on_status
        self.thread = None
        self.stop_event = threading.Event()
        self.loop = None
        self.storage = None
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
            name="MONOLITH-Apple-TV",
            daemon=True,
        )
        self.thread.start()

        print(
            "[APPLE TV] "
            f"pyatv-Monitor für {APPLE_TV_IP} gestartet"
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
        self.storage = FileStorage(
            APPLE_TV_STORAGE_FILE,
            self.loop,
        )
        await self.storage.load()

        while not self.stop_event.is_set():
            try:
                config = await self._find_apple_tv()

                if config is None:
                    self._publish_unavailable()
                else:
                    await self._publish_config(
                        config
                    )

            except Exception as error:
                self._publish_unavailable(
                    error=str(error),
                )

            if not self.stop_event.is_set():
                await asyncio.sleep(
                    APPLE_TV_SCAN_INTERVAL_SECONDS
                )

    async def _find_apple_tv(self):
        if not (APPLE_TV_IP or APPLE_TV_IDENTIFIER):
            return None

        configs = await pyatv.scan(
            self.loop,
            timeout=APPLE_TV_SCAN_TIMEOUT_SECONDS,
            hosts=(
                [APPLE_TV_IP]
                if APPLE_TV_IP
                else None
            ),
            storage=self.storage,
        )

        for config in configs:
            identifier = (
                config.identifier or ""
            ).upper()

            if (
                APPLE_TV_IDENTIFIER
                and identifier
                == APPLE_TV_IDENTIFIER
            ):
                return config

        for config in configs:
            if (
                not APPLE_TV_NAME
                or config.name.casefold()
                == APPLE_TV_NAME.casefold()
            ):
                return config

        return None

    async def _publish_config(
        self,
        config,
    ):
        device_info = config.device_info
        playback = await self._get_playback(
            config
        )

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
            "power_state": playback["power_state"],
            "title": playback["title"],
            "artist": playback["artist"],
            "artwork": playback["artwork"],
            "address": str(config.address),
            "identifier": config.identifier,
            "model": str(device_info.model.name),
            "operating_system": str(
                device_info.operating_system.name
            ),
            "version": device_info.version or None,
            "last_seen": self._now_iso(),
            "error": None,
        })

        if self.last_connected is not True:
            print(
                "[APPLE TV] "
                f"{config.name} erreichbar "
                f"({config.address}) · "
                f"{device_info}"
            )

        self.last_connected = True

    async def _get_playback(
        self,
        config,
    ):
        apple_tv = None

        try:
            settings = await self.storage.get_settings(
                config
            )
            settings.protocols.airplay.mrp_tunnel = (
                MrpTunnel.Force
            )

            apple_tv = await pyatv.connect(
                config,
                self.loop,
                storage=self.storage,
            )
            await asyncio.sleep(0.5)
            playing = await apple_tv.metadata.playing()
            metadata_active = playing.device_state in {
                DeviceState.Loading,
                DeviceState.Playing,
                DeviceState.Seeking,
            }
            companion_active = (
                apple_tv.features.get_feature(
                    FeatureName.Pause
                ).state
                == FeatureState.Available
            )
            power_active = (
                apple_tv.power.power_state
                == PowerState.On
            )
            power_state = (
                apple_tv.power.power_state.name.lower()
            )
            power_fallback_active = (
                power_active
                and playing.device_state
                == DeviceState.Idle
                and not playing.title
            )
            active = (
                metadata_active
                or companion_active
                or power_fallback_active
            )
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
                "power_state": power_state,
                "playback_state": (
                    playing.device_state.name.lower()
                    if metadata_active
                    else (
                        "playing"
                        if (
                            companion_active
                            or power_fallback_active
                        )
                        else "paused"
                    )
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
            return self._paused_playback()

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
            "value": "Paused",
            "connected": False,
            **self._paused_playback(),
            "address": APPLE_TV_IP or None,
            "last_seen": None,
            "error": error,
        })

        if self.last_connected is not False:
            print(
                "[APPLE TV] "
                "Apple TV nicht erreichbar"
                + (
                    f": {error}"
                    if error
                    else ""
                )
            )

        self.last_connected = False

    @staticmethod
    def _paused_playback():
        return {
            "playing": False,
            "power_state": "unknown",
            "playback_state": "paused",
            "title": None,
            "artist": None,
            "artwork": None,
        }

    @staticmethod
    def _now_iso():
        return datetime.now().astimezone().isoformat(
            timespec="seconds"
        )


apple_tv_monitor = None


def start_apple_tv_monitor(
    on_status,
):
    global apple_tv_monitor

    if apple_tv_monitor is None:
        apple_tv_monitor = AppleTvMonitor(
            on_status
        )

    apple_tv_monitor.start()


def stop_apple_tv_monitor():
    if apple_tv_monitor is not None:
        with suppress(Exception):
            apple_tv_monitor.stop()
