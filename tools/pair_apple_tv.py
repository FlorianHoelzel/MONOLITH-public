import asyncio
import sys

import pyatv
from pyatv.const import Protocol
from pyatv.settings import MrpTunnel
from pyatv.storage.file_storage import FileStorage

from monolith.apple_tv import (
    APPLE_TV_IDENTIFIER,
    APPLE_TV_IP,
    APPLE_TV_STORAGE_FILE,
)


async def main():
    loop = asyncio.get_running_loop()
    storage = FileStorage(
        APPLE_TV_STORAGE_FILE,
        loop,
    )
    await storage.load()

    configs = await pyatv.scan(
        loop,
        timeout=5,
        hosts=[APPLE_TV_IP],
        storage=storage,
    )

    config = next(
        (
            item
            for item in configs
            if (
                item.identifier or ""
            ).upper()
            == APPLE_TV_IDENTIFIER
        ),
        None,
    )

    if config is None:
        raise RuntimeError(
            "Apple TV wurde nicht gefunden"
        )

    protocol = (
        Protocol.Companion
        if (
            len(sys.argv) > 1
            and sys.argv[1].casefold()
            == "companion"
        )
        else Protocol.AirPlay
    )

    pairing = await pyatv.pair(
        config,
        protocol,
        loop,
        storage=storage,
        name="MONOLITH",
    )

    try:
        await pairing.begin()

        print(
            "Auf dem Apple TV wird jetzt ein PIN angezeigt "
            f"({protocol.name})."
        )
        pin = await asyncio.to_thread(
            input,
            "PIN: ",
        )
        pairing.pin(pin.strip())
        await pairing.finish()

        if not pairing.has_paired:
            raise RuntimeError(
                "Kopplung wurde nicht bestätigt"
            )

        if protocol == Protocol.AirPlay:
            settings = await storage.get_settings(
                config
            )
            settings.protocols.airplay.mrp_tunnel = (
                MrpTunnel.Force
            )
        await storage.save()

        print(
            "Apple TV wurde erfolgreich mit MONOLITH gekoppelt."
        )

    finally:
        await pairing.close()


if __name__ == "__main__":
    asyncio.run(main())
