import json
import os
import subprocess
import threading
import time

from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fritzconnection.lib.fritzhosts import FritzHosts

from monolith.data_paths import data_path
from monolith.database import (
    get_recent_events,
    save_event,
)


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


# =============================================================
# CONFIG
# =============================================================

CHECK_INTERVAL_SECONDS = 30

# Eine Person wird erst als abwesend markiert, wenn ALLE zugeordneten
# Geräte 20 Minuten lang weder von der FRITZ!Box gesehen werden noch
# auf eine direkte Netzwerkanfrage vom Pi antworten.
#
# Sobald mindestens ein Gerät wieder auftaucht,
# wird der Abwesenheits-Timer verworfen.
#
# Der zweite Nachweis verhindert, dass ein schlafendes Apple-Gerät nur
# wegen eines vorübergehend falschen FRITZ!-Hoststatus als weg gilt.
# Ankunft wird weiterhin sofort erkannt.
try:
    AWAY_AFTER_SECONDS = max(
        5 * 60,
        int(
            os.getenv(
                "PRESENCE_AWAY_AFTER_SECONDS",
                str(20 * 60),
            )
        ),
    )
except ValueError:
    AWAY_AFTER_SECONDS = 20 * 60

try:
    DEVICE_PROBE_TIMEOUT_SECONDS = max(
        1,
        int(
            os.getenv(
                "PRESENCE_PROBE_TIMEOUT_SECONDS",
                "2",
            )
        ),
    )
except ValueError:
    DEVICE_PROBE_TIMEOUT_SECONDS = 2


PEOPLE = {
    "person_1": {
        "name": os.getenv("PRESENCE_PERSON_1_NAME", "Person 1"),

        "devices": [
            {
                "id": "device_1",
                "name": "Gerät 1",
                "ip": os.getenv("PRESENCE_PERSON_1_DEVICE_1_IP", ""),
                "mac": os.getenv("PRESENCE_PERSON_1_DEVICE_1_MAC", ""),
            },
        ],
    },

    "person_2": {
        "name": os.getenv("PRESENCE_PERSON_2_NAME", "Person 2"),

        "devices": [
            {
                "id": "device_1",
                "name": "Gerät 1",
                "ip": os.getenv("PRESENCE_PERSON_2_DEVICE_1_IP", ""),
                "mac": os.getenv("PRESENCE_PERSON_2_DEVICE_1_MAC", ""),
            },

            {
                "id": "device_2",
                "name": "Gerät 2",
                "ip": os.getenv("PRESENCE_PERSON_2_DEVICE_2_IP", ""),
                "mac": os.getenv("PRESENCE_PERSON_2_DEVICE_2_MAC", ""),
            },
        ],
    },
}


# =============================================================
# FILES
# =============================================================

STATE_FILE = data_path("presence_state.json")


# =============================================================
# HELPERS
# =============================================================

def parse_timestamp(value):
    if (
        value is None
        or value == ""
    ):
        return None


    if isinstance(
        value,
        (int, float),
    ):
        timestamp = float(
            value
        )

        if (
            timestamp
            > 100000000000
        ):
            timestamp /= 1000

        return timestamp


    text = (
        str(value)
        .strip()
    )


    if not text:
        return None


    try:
        timestamp = float(
            text
        )

        if (
            timestamp
            > 100000000000
        ):
            timestamp /= 1000

        return timestamp

    except ValueError:
        pass


    try:
        normalized = (
            text
            .replace(
                "Z",
                "+00:00",
            )
        )


        date = (
            datetime
            .fromisoformat(
                normalized
            )
        )


        return date.timestamp()

    except ValueError:
        return None


# =============================================================
# PRESENCE MONITOR
# =============================================================

class PresenceMonitor:
    def __init__(self):
        self.running = False

        self.thread = None

        self.lock = (
            threading.RLock()
        )

        self.fritz_hosts = None

        self.people_state = {}


        for (
            person_id,
            person,
        ) in PEOPLE.items():

            device_status = {}


            for device in person[
                "devices"
            ]:
                device_status[
                    device["id"]
                ] = None


            self.people_state[
                person_id
            ] = {
                "home": None,
                "last_seen": None,
                "missing_since": None,
                "status_since": None,
                "device_status": device_status,
                "manual_home_until_seen": False,
            }


        self.restore_presence_state()


    # =========================================================
    # STATE FILE
    # =========================================================

    def save_presence_state(self):
        with self.lock:
            data = {}


            for (
                person_id,
                state,
            ) in self.people_state.items():

                data[
                    person_id
                ] = {
                    "manual_home_until_seen": state.get("manual_home_until_seen", False),
                    "home":
                        state[
                            "home"
                        ],

                    "status_since":
                        state[
                            "status_since"
                        ],

                    "missing_since":
                        state[
                            "missing_since"
                        ],
                }


            try:
                with open(
                    STATE_FILE,
                    "w",
                    encoding="utf-8",
                ) as file:

                    json.dump(
                        data,
                        file,
                        ensure_ascii=False,
                        indent=2,
                    )

            except OSError as error:
                print(
                    "[PRESENCE ERROR] "
                    "Status konnte nicht gespeichert werden: "
                    f"{error}"
                )


    # ---------------------------------------------------------
    # RESTORE FROM FILE
    # ---------------------------------------------------------

    def restore_from_state_file(self):
        if not STATE_FILE.exists():
            return False


        try:
            with open(
                STATE_FILE,
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(
                    file
                )

        except (
            OSError,
            json.JSONDecodeError,
        ) as error:

            print(
                "[PRESENCE ERROR] "
                "Presence-State konnte nicht geladen werden: "
                f"{error}"
            )

            return False


        restored_any = False


        for (
            person_id,
            saved_state,
        ) in data.items():

            if (
                person_id
                not in self.people_state
            ):
                continue


            home = (
                saved_state.get(
                    "home"
                )
            )


            status_since = (
                parse_timestamp(
                    saved_state.get(
                        "status_since"
                    )
                )
            )


            if (
                home
                not in [
                    True,
                    False,
                ]
            ):
                continue


            state = (
                self.people_state[
                    person_id
                ]
            )


            state[
                "home"
            ] = home


            state[
                "status_since"
            ] = status_since


            state[
                "missing_since"
            ] = None  # Während eines Neustarts wurde nicht weiter beobachtet.

            state["manual_home_until_seen"] = (
                home is True and saved_state.get("manual_home_until_seen") is True
            )


            restored_any = True


        return restored_any


    # ---------------------------------------------------------
    # RESTORE FROM ACTIVITY FEED
    # ---------------------------------------------------------

    def restore_from_events(self):
        try:
            events = (
                get_recent_events(
                    1000
                )
            )

        except Exception as error:
            print(
                "[PRESENCE ERROR] "
                "Presence-Events konnten nicht "
                "wiederhergestellt werden: "
                f"{error}"
            )

            return


        for (
            person_id,
            person,
        ) in PEOPLE.items():

            current_state = (
                self.people_state[
                    person_id
                ]
            )


            if (
                current_state[
                    "home"
                ]
                is not None
                and current_state[
                    "status_since"
                ]
                is not None
            ):
                continue


            expected_source = (
                f"presence_{person_id}"
            )


            newest_event = None
            newest_timestamp = None


            for event in events:
                source_id = (
                    event.get(
                        "source_id"
                    )
                    or event.get(
                        "source"
                    )
                )


                if (
                    source_id
                    != expected_source
                ):
                    continue


                timestamp = (
                    parse_timestamp(
                        event.get(
                            "created_at"
                        )
                        or event.get(
                            "recorded_at"
                        )
                        or event.get(
                            "timestamp"
                        )
                        or event.get(
                            "time"
                        )
                    )
                )


                if timestamp is None:
                    if newest_event is None:
                        newest_event = event

                    continue


                if (
                    newest_timestamp is None
                    or timestamp
                    > newest_timestamp
                ):
                    newest_event = event
                    newest_timestamp = timestamp


            if newest_event is None:
                continue


            title = (
                str(
                    newest_event.get(
                        "title",
                        "",
                    )
                )
                .lower()
            )


            if (
                "nach hause gekommen"
                in title
            ):
                home = True

            elif (
                "haus verlassen"
                in title
            ):
                home = False

            else:
                continue


            current_state[
                "home"
            ] = home


            current_state[
                "status_since"
            ] = newest_timestamp


            print(
                "[PRESENCE] "
                f"{person['name']} Status "
                "aus Verlauf wiederhergestellt"
            )


    # ---------------------------------------------------------
    # COMPLETE RESTORE
    # ---------------------------------------------------------

    def restore_presence_state(self):
        restored_file = (
            self.restore_from_state_file()
        )


        self.restore_from_events()


        if restored_file:
            print(
                "[PRESENCE] "
                "Gespeicherter Anwesenheitsstatus geladen"
            )


        self.save_presence_state()


    # =========================================================
    # FRITZ CONNECTION
    # =========================================================

    def connect_fritzbox(self):
        if (
            not FRITZBOX_ADDRESS
            or not FRITZBOX_USER
            or not FRITZBOX_PASSWORD
        ):
            print(
                "[PRESENCE ERROR] "
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

                    timeout=5,
                )
            )


            return True


        except Exception as error:
            print(
                "[PRESENCE ERROR] "
                "FRITZ!Box Verbindung fehlgeschlagen: "
                f"{error}"
            )


            self.fritz_hosts = None


            return False


    # =========================================================
    # START
    # =========================================================

    def start(self):
        if self.running:
            return


        self.running = True


        self.connect_fritzbox()


        self.thread = (
            threading.Thread(
                target=
                    self.monitor_loop,

                daemon=
                    True,

                name=
                    "MONOLITH-Presence",
            )
        )


        self.thread.start()


        print(
            "[PRESENCE] "
            "Anwesenheitserkennung gestartet"
        )


    # =========================================================
    # FRITZBOX DEVICE STATUS
    # =========================================================

    def get_router_hosts(self):
        # One host-list request per polling round, shared by all devices.
        now = time.monotonic()
        if now - getattr(self, "router_hosts_checked_at", -float("inf")) < CHECK_INTERVAL_SECONDS:
            return self.router_hosts
        self.router_hosts_checked_at = now
        self.router_hosts = None
        try:
            self.router_hosts = self.fritz_hosts.get_hosts_attributes()
        except Exception as error:
            print(f"[PRESENCE] Erweiterte Hostliste nicht verfügbar: {type(error).__name__}")
        return self.router_hosts

    def get_device_status(self, mac, ip=None):
        if not mac:
            return None
        if self.fritz_hosts is None and not self.connect_fritzbox():
            return True if self.probe_device(ip, mac) is True else None

        expected_mac = mac.upper()
        try:
            # The extended list also covers MAC aliases recorded by FRITZ!OS.
            hosts = self.get_router_hosts()
            matching = []
            for host in hosts or []:
                addresses = str(host.get("X_AVM-DE_MACAddressList") or "").replace(",", " ").split()
                addresses.append(str(host.get("MACAddress") or ""))
                if expected_mac in [address.upper() for address in addresses]:
                    matching.append(host)
            if matching:
                if any(host.get("Active") is True for host in matching):
                    return True
                fritz_status = False if all(host.get("Active") is False for host in matching) else None
                candidates = [(host.get("IPAddress"), host.get("MACAddress") or mac) for host in matching]
            else:
                entry = self.fritz_hosts.get_specific_host_entry(mac)
                fritz_status = entry.get("NewActive")
                candidates = [(entry.get("NewIPAddress"), mac)]
            if fritz_status is True:
                return True
            # Only an address tied to the expected MAC can confirm presence.
            # Fixed configured IPs may have been reassigned to another device.
            if not any(address for address, _ in candidates):
                candidates = [(ip, mac)]
            probe_unknown = False
            for address, device_mac in candidates:
                probe = self.probe_device(address, device_mac)
                if probe is True:
                    return True
                probe_unknown |= probe is None
            if probe_unknown:
                return None
            return fritz_status if isinstance(fritz_status, bool) else None
        except Exception as error:
            print(f"[PRESENCE ERROR] FRITZ!Box Abfrage fehlgeschlagen: {type(error).__name__}")
            self.fritz_hosts = None
            self.router_hosts_checked_at = -float("inf")
            return True if self.probe_device(ip, mac) is True else None

    @staticmethod
    def probe_device(ip, mac=None):
        import ipaddress

        try:
            address = str(ipaddress.IPv4Address(ip))
        except (ipaddress.AddressValueError, ValueError, TypeError):
            return None
        command = (
            ["ping", "-n", "1", "-w", str(DEVICE_PROBE_TIMEOUT_SECONDS * 1000), address]
            if os.name == "nt" else
            ["ping", "-c", "1", "-W", str(DEVICE_PROBE_TIMEOUT_SECONDS), address]
        )
        try:
            result = subprocess.run(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=DEVICE_PROBE_TIMEOUT_SECONDS + 1, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

        if not mac:
            return result.returncode == 0
        if os.name == "nt":
            # Windows is used only for development. Its ARP cache does not
            # expose freshness; do not treat it as proof of presence.
            return None
        try:
            neighbors = subprocess.run(
                ["ip", "-j", "neigh", "show", "to", address],
                capture_output=True, text=True, timeout=2, check=False,
            )
            if neighbors.returncode != 0:
                return None
            for neighbor in json.loads(neighbors.stdout):
                if (neighbor.get("dst") == address
                    and str(neighbor.get("lladdr", "")).upper() == mac.upper()
                    and "REACHABLE" in neighbor.get("state", [])):
                    return True
        except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
            return None
        # A failed ping or a stale ARP entry cannot confirm presence.
        return False


    # =========================================================
    # PERSON DEVICE STATUS
    # =========================================================

    def get_person_device_status(
        self,
        person_id,
    ):
        person = PEOPLE[
            person_id
        ]


        statuses = {}

        online_devices = []

        has_unknown = False


        for device in person[
            "devices"
        ]:

            device_id = (
                device[
                    "id"
                ]
            )


            status = (
                self.get_device_status(
                    device["mac"],
                    device.get("ip"),
                )
            )


            statuses[
                device_id
            ] = status


            if (
                status
                is True
            ):
                online_devices.append(
                    device[
                        "name"
                    ]
                )


            elif (
                status
                is None
            ):
                has_unknown = True


        return {
            "statuses":
                statuses,

            "online_devices":
                online_devices,

            "any_online":
                len(
                    online_devices
                ) > 0,

            "has_unknown":
                has_unknown,
        }


    # =========================================================
    # EVENT
    # =========================================================

    def create_presence_event(
        self,
        person_id,
        home,
        occurred_at=None,
    ):
        person = PEOPLE[
            person_id
        ]


        name = person[
            "name"
        ]


        if home:
            title = (
                f"{name} ist nach Hause gekommen"
            )

        else:
            title = (
                f"{name} hat das Haus verlassen"
            )


        save_event(
            event_type=
                "presence",

            source_id=
                f"presence_{person_id}",

            room=
                "Anwesenheit",

            title=
                title,

            created_at=
                occurred_at,
        )


        print(
            "[PRESENCE] "
            f"{title}"
        )


    # =========================================================
    # PROCESS PERSON
    # =========================================================

    def process_person(
        self,
        person_id,
    ):
        person = PEOPLE[
            person_id
        ]


        result = (
            self.get_person_device_status(
                person_id
            )
        )


        statuses = (
            result[
                "statuses"
            ]
        )


        any_online = (
            result[
                "any_online"
            ]
        )


        has_unknown = (
            result[
                "has_unknown"
            ]
        )


        online_devices = (
            result[
                "online_devices"
            ]
        )


        now = time.time()

        event_to_create = None

        event_occurred_at = None


        with self.lock:
            state = (
                self.people_state[
                    person_id
                ]
            )


            state[
                "device_status"
            ] = statuses


            # =================================================
            # MINDESTENS EIN GERÄT ONLINE
            # =================================================

            if any_online:
                if state.get("manual_home_until_seen"):
                    state["manual_home_until_seen"] = False
                    self.save_presence_state()
                state[
                    "last_seen"
                ] = now


                # Sobald irgendein persönliches Gerät
                # wieder gesehen wird, wird ein eventuell
                # laufender Away-Timer komplett verworfen.
                if (
                    state[
                        "missing_since"
                    ]
                    is not None
                ):
                    state[
                        "missing_since"
                    ] = None


                    self.save_presence_state()


                # ---------------------------------------------
                # Noch kein Status bekannt
                # ---------------------------------------------

                if (
                    state[
                        "home"
                    ]
                    is None
                ):
                    state[
                        "home"
                    ] = True


                    if (
                        state[
                            "status_since"
                        ]
                        is None
                    ):
                        state[
                            "status_since"
                        ] = now


                    self.save_presence_state()


                    devices_text = (
                        ", ".join(
                            online_devices
                        )
                    )


                    print(
                        "[PRESENCE] "
                        f"{person['name']} -> Zuhause "
                        f"({devices_text})"
                    )


                    return


                # ---------------------------------------------
                # Person war vorher weg
                # ---------------------------------------------

                if (
                    state[
                        "home"
                    ]
                    is False
                ):
                    state[
                        "home"
                    ] = True


                    state[
                        "status_since"
                    ] = now


                    state[
                        "missing_since"
                    ] = None


                    self.save_presence_state()


                    event_to_create = True


                # ---------------------------------------------
                # Person war bereits zuhause
                # ---------------------------------------------

                else:
                    if (
                        state[
                            "status_since"
                        ]
                        is None
                    ):
                        state[
                            "status_since"
                        ] = now


                        self.save_presence_state()


            # =================================================
            # KEIN GERÄT ONLINE, ABER STATUS UNKLAR
            # =================================================

            elif has_unknown:
                # Wenn mindestens eine FRITZ!Box-Abfrage
                # fehlschlägt, behandeln wir das NICHT
                # als bestätigte Abwesenheit.
                # Unklare Zeit darf nicht zum Offline-Timer zählen.
                if state["missing_since"] is not None:
                    state["missing_since"] = None
                    self.save_presence_state()
                return


            # =================================================
            # ALLE GERÄTE OFFLINE
            # =================================================

            else:
                # Eine manuell bestätigte Anwesenheit gilt, bis ein Gerät
                # wieder gesehen wurde und die normale Erkennung übernimmt.
                if state.get("manual_home_until_seen"):
                    return
                # Beim ersten vollständig negativen Check
                # merken wir uns den Zeitpunkt.
                if (
                    state[
                        "missing_since"
                    ]
                    is None
                ):
                    state[
                        "missing_since"
                    ] = now


                    self.save_presence_state()


                missing_for = (
                    now
                    - state[
                        "missing_since"
                    ]
                )


                # ---------------------------------------------
                # Noch kein bekannter Status
                # ---------------------------------------------

                if (
                    state[
                        "home"
                    ]
                    is None
                ):
                    if (
                        missing_for
                        >= AWAY_AFTER_SECONDS
                    ):
                        state[
                            "home"
                        ] = False


                        state[
                            "status_since"
                        ] = state[
                            "missing_since"
                        ]


                        self.save_presence_state()


                        print(
                            "[PRESENCE] "
                            f"{person['name']} -> Abwesend"
                        )


                # ---------------------------------------------
                # Person war bisher zuhause
                # ---------------------------------------------

                elif (
                    state[
                        "home"
                    ]
                    is True
                ):
                    if (
                        missing_for
                        >= AWAY_AFTER_SECONDS
                    ):
                        state[
                            "home"
                        ] = False


                        # Die Abwesenheit zählt ab dem
                        # ersten Zeitpunkt, an dem wirklich
                        # ALLE Geräte verschwunden waren.
                        state[
                            "status_since"
                        ] = state[
                            "missing_since"
                        ]


                        self.save_presence_state()


                        event_to_create = False


                        event_occurred_at = state[
                            "missing_since"
                        ]


                # ---------------------------------------------
                # Person ist bereits abwesend
                # ---------------------------------------------

                else:
                    if (
                        state[
                            "status_since"
                        ]
                        is None
                    ):
                        state[
                            "status_since"
                        ] = (
                            state[
                                "missing_since"
                            ]
                            or now
                        )


                        self.save_presence_state()


        # =====================================================
        # EVENT
        # =====================================================

        if (
            event_to_create
            is not None
        ):
            self.create_presence_event(
                person_id,
                event_to_create,
                event_occurred_at,
            )


    # =========================================================
    # STATUS API
    # =========================================================

    def get_status(self):
        people = {}


        with self.lock:
            for (
                person_id,
                person,
            ) in PEOPLE.items():

                state = (
                    self.people_state[
                        person_id
                    ]
                )


                devices = []


                for device in person[
                    "devices"
                ]:

                    device_id = (
                        device[
                            "id"
                        ]
                    )


                    devices.append({
                        "id":
                            device_id,

                        "name":
                            device[
                                "name"
                            ],

                        "ip":
                            device.get(
                                "ip"
                            ),

                        "online":
                            state[
                                "device_status"
                            ].get(
                                device_id
                            ),
                    })


                people[
                    person_id
                ] = {
                    "name":
                        person[
                            "name"
                        ],

                    "configured":
                        len(
                            person[
                                "devices"
                            ]
                        ) > 0,

                    "home":
                        state[
                            "home"
                        ],

                    "last_seen":
                        state[
                            "last_seen"
                        ],

                    "status_since":
                        state[
                            "status_since"
                        ],

                    "devices":
                        devices,
                }


        return {
            "people":
                people,

            "checked_at":
                time.time(),
        }


    # =========================================================
    # LOOP
    # =========================================================

    def monitor_loop(self):
        while self.running:

            for person_id in PEOPLE:

                try:
                    self.process_person(
                        person_id
                    )

                except Exception as error:
                    print(
                        "[PRESENCE ERROR] "
                        f"{person_id}: "
                        f"{error}"
                    )


            time.sleep(
                CHECK_INTERVAL_SECONDS
            )


# =============================================================
# GLOBAL MONITOR
# =============================================================

presence_monitor = (
    PresenceMonitor()
)


def start_presence_monitor():
    presence_monitor.start()


def get_presence_status():
    return (
        presence_monitor
        .get_status()
    )
