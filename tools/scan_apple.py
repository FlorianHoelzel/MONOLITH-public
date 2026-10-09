import asyncio

import pyatv


async def main():
    print("Suche Apple TV / HomePod im Netzwerk...")
    print()

    loop = asyncio.get_running_loop()

    devices = await pyatv.scan(
        loop,
        timeout=5,
    )

    if not devices:
        print("Keine Geräte gefunden.")
        return

    print(f"{len(devices)} Gerät(e) gefunden:")
    print()

    for index, device in enumerate(devices, start=1):
        print("=" * 50)

        print(f"Gerät {index}")
        print(f"Name: {device.name}")
        print(f"IP: {device.address}")
        print(f"Identifier: {device.identifier}")
        print(f"Device Info: {device.device_info}")

        print()
        print("Services:")

        for service in device.services:
            print(
                f"  - {service.protocol.name}"
                f" | Port {service.port}"
            )

        print()

    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())