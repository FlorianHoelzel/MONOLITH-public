import asyncio
import copy
import json
from pathlib import Path

import aiohttp
from aiowebostv.handshake import (
    REGISTRATION_MESSAGE,
)

from monolith.lg_tv import (
    LG_TV_IP,
    LG_TV_KEY_FILE,
)


PAIRING_TYPE = "LGSWITCH-PIN"
RECEIVE_TIMEOUT_SECONDS = 30


async def receive_json(
    websocket,
):
    return await websocket.receive_json(
        timeout=RECEIVE_TIMEOUT_SECONDS
    )


async def pair():
    timeout = aiohttp.ClientTimeout(
        total=None,
        connect=5,
    )

    async with aiohttp.ClientSession(
        timeout=timeout,
    ) as session:
        async with session.ws_connect(
            f"wss://{LG_TV_IP}:3001",
            ssl=False,
            heartbeat=5,
            max_msg_size=8 * 1024 * 1024,
        ) as websocket:
            await websocket.send_json({
                "id": "hello",
                "type": "hello",
                "payload": {},
            })
            hello = await receive_json(
                websocket
            )

            pairing_types = (
                hello.get("payload", {})
                .get("pairingTypes", [])
            )

            if PAIRING_TYPE not in pairing_types:
                raise RuntimeError(
                    "Der TV bietet LGSWITCH-PIN "
                    "nicht an"
                )

            await websocket.send_json({
                "id": "get_sys_info",
                "type": "request",
                "uri": (
                    "ssap://system/getSystemInfo"
                ),
                "payload": {},
            })
            await receive_json(
                websocket
            )

            registration = copy.deepcopy(
                REGISTRATION_MESSAGE
            )
            registration["payload"][
                "client-key"
            ] = None
            registration["payload"][
                "pairingType"
            ] = PAIRING_TYPE

            await websocket.send_json(
                registration
            )

            response = await receive_json(
                websocket
            )

            response_type = response.get(
                "type"
            )
            response_pairing_type = (
                response.get("payload", {})
                .get("pairingType")
            )

            if response_type == "error":
                raise RuntimeError(
                    response.get(
                        "error",
                        "Kopplung abgelehnt",
                    )
                )

            if response_pairing_type not in {
                "PIN",
                "LGSWITCH-PIN",
            }:
                raise RuntimeError(
                    "Unerwartete Pairing-Antwort: "
                    f"{response_pairing_type or response_type}"
                )

            pin = input(
                "PIN vom Fernseher: "
            ).strip()

            await websocket.send_json({
                "type": "request",
                "id": "register_1",
                "uri": "ssap://pairing/setPin",
                "payload": {
                    "pin": pin,
                },
            })

            result = await receive_json(
                websocket
            )

            if result.get("type") != "registered":
                raise RuntimeError(
                    result.get(
                        "error",
                        "Kopplung fehlgeschlagen",
                    )
                )

            client_key = (
                result.get("payload", {})
                .get("client-key")
            )

            if not client_key:
                raise RuntimeError(
                    "Der TV hat keinen Schlüssel geliefert"
                )

            Path(
                LG_TV_KEY_FILE
            ).write_text(
                json.dumps(
                    {
                        "client_key": client_key,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            print(
                "LG-TV erfolgreich gekoppelt."
            )


if __name__ == "__main__":
    asyncio.run(
        pair()
    )
