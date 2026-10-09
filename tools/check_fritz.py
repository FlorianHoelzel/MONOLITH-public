import os

from dotenv import load_dotenv
from fritzconnection.lib.fritzhosts import FritzHosts


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


DEVICE_MAC = os.getenv("DIAGNOSTIC_DEVICE_MAC", "")


def main():
    print(
        "[FRITZ] Verbinde mit "
        f"{FRITZBOX_ADDRESS} ..."
    )

    hosts = FritzHosts(
        address=FRITZBOX_ADDRESS,
        user=FRITZBOX_USER,
        password=FRITZBOX_PASSWORD,
    )

    print(
        "[FRITZ] Verbindung erfolgreich"
    )

    status = hosts.get_host_status(
        DEVICE_MAC
    )

    print(
        "[FRITZ] Diagnosegerät "
        f"{DEVICE_MAC} -> "
        f"{status}"
    )


if __name__ == "__main__":
    main()