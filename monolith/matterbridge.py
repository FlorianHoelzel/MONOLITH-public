import asyncio
import json
import os
import threading
from contextlib import suppress

import aiohttp


MATTERBRIDGE_WS_URL = os.getenv(
    "MATTERBRIDGE_WS_URL",
    "ws://127.0.0.1:8283/devices",
)

ROBOVAC_PLUGIN = "matterbridge-eufy-g30"
ROBOVAC_SERIAL = os.getenv("ROBOVAC_SERIAL", "").strip()

ROBOVAC_OPERATIONAL_STATES = {
    1: "cleaning",
    2: "paused",
    64: "returning_to_dock",
    65: "charging",
    66: "docked",
}


def normalize_robovac_status(value):
    try:
        operational_state = int(value)
    except (TypeError, ValueError):
        return "Unbekannt"

    return ROBOVAC_OPERATIONAL_STATES.get(
        operational_state,
        "Unbekannt",
    )


class MatterbridgeRobovacMonitor:
    def __init__(self, on_status):
        self.on_status = on_status
        self.thread = None
        self.stop_event = threading.Event()
        self.request_id = 830001

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._run,
            name="matterbridge-robovac",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run(self):
        asyncio.run(
            self._monitor_forever()
        )

    async def _monitor_forever(self):
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=5,
        )

        async with aiohttp.ClientSession(
            timeout=timeout,
        ) as session:
            while not self.stop_event.is_set():
                try:
                    await self._monitor_connection(
                        session
                    )
                except (
                    aiohttp.ClientError,
                    asyncio.TimeoutError,
                    OSError,
                ) as error:
                    self.on_status(
                        "Unbekannt"
                    )
                    print(
                        "[MATTERBRIDGE] "
                        "Robovac nicht erreichbar: "
                        f"{error}"
                    )

                if not self.stop_event.is_set():
                    await asyncio.sleep(5)

    async def _monitor_connection(
        self,
        session,
    ):
        async with session.ws_connect(
            MATTERBRIDGE_WS_URL,
            heartbeat=30,
        ) as websocket:
            device = await self._find_robovac(
                websocket
            )

            if device is None:
                self.on_status(
                    "Unbekannt"
                )
                raise OSError(
                    "Eufy RoboVac nicht registriert"
                )

            await self._read_initial_status(
                websocket,
                device,
            )

            async for message in websocket:
                if self.stop_event.is_set():
                    return

                if (
                    message.type
                    == aiohttp.WSMsgType.TEXT
                ):
                    self._handle_message(
                        json.loads(
                            message.data
                        )
                    )

                elif message.type in {
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                }:
                    break

    async def _find_robovac(
        self,
        websocket,
    ):
        response = await self._request(
            websocket,
            "/api/devices",
            {},
        )

        for device in response or []:
            if (
                device.get("pluginName")
                == ROBOVAC_PLUGIN
                and device.get("serial")
                == ROBOVAC_SERIAL
            ):
                return device

        return None

    async def _read_initial_status(
        self,
        websocket,
        device,
    ):
        response = await self._request(
            websocket,
            "/api/clusters",
            {
                "plugin": ROBOVAC_PLUGIN,
                "endpoint": device.get(
                    "endpoint",
                    1,
                ),
                "uniqueId": device[
                    "uniqueId"
                ],
            },
        )

        for attribute in (
            response or {}
        ).get("clusters", []):
            if (
                attribute.get("clusterName")
                == "RvcOperationalState"
                and attribute.get(
                    "attributeName"
                )
                == "operationalState"
            ):
                self.on_status(
                    normalize_robovac_status(
                        attribute.get(
                            "attributeLocalValue"
                        )
                    )
                )
                return

        self.on_status(
            "Unbekannt"
        )

    async def _request(
        self,
        websocket,
        method,
        params,
    ):
        self.request_id += 1
        request_id = self.request_id

        await websocket.send_json({
            "id": request_id,
            "sender": "MONOLITH",
            "method": method,
            "src": "Frontend",
            "dst": "Matterbridge",
            "params": params,
        })

        while True:
            message = await asyncio.wait_for(
                websocket.receive(),
                timeout=10,
            )

            if (
                message.type
                != aiohttp.WSMsgType.TEXT
            ):
                raise OSError(
                    "Matterbridge WebSocket geschlossen"
                )

            data = json.loads(
                message.data
            )

            if (
                data.get("id")
                == request_id
                and data.get("method")
                == method
            ):
                if not data.get(
                    "success",
                    False,
                ):
                    raise OSError(
                        data.get(
                            "error",
                            f"Fehler bei {method}",
                        )
                    )

                return data.get(
                    "response"
                )

            self._handle_message(
                data
            )

    def _handle_message(
        self,
        data,
    ):
        if (
            data.get("method")
            != "state_update"
        ):
            return

        response = data.get(
            "response",
            {},
        )

        if (
            response.get("plugin")
            != ROBOVAC_PLUGIN
            or response.get("serialNumber")
            != ROBOVAC_SERIAL
            or response.get("cluster")
            != "RvcOperationalState"
            or response.get("attribute")
            != "operationalState"
        ):
            return

        self.on_status(
            normalize_robovac_status(
                response.get("value")
            )
        )


robovac_monitor = None


def start_robovac_monitor(
    on_status,
):
    global robovac_monitor

    if robovac_monitor is None:
        robovac_monitor = (
            MatterbridgeRobovacMonitor(
                on_status
            )
        )

    robovac_monitor.start()


def stop_robovac_monitor():
    if robovac_monitor is not None:
        with suppress(Exception):
            robovac_monitor.stop()
