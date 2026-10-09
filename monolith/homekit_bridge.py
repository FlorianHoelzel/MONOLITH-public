import json
import math
import os
import tempfile
import time

import requests

from dotenv import load_dotenv

from monolith.data_paths import data_path
from monolith.devices import devices
from monolith.homekit_config import read_homekit_pin

from pyhap.accessory import (
    Accessory,
    Bridge,
)

from pyhap.accessory_driver import (
    AccessoryDriver,
)

from pyhap.const import (
    CATEGORY_SWITCH,
)


# =============================================================
# CONFIG
# =============================================================

MONOLITH_STATE_API = (
    "http://127.0.0.1:5000/api/state"
)

MONOLITH_EVENT_API = (
    "http://127.0.0.1:5000/api/event"
)


HOMEKIT_PORT = 51850

load_dotenv()
HOMEKIT_PIN = read_homekit_pin()

STATE_FILE = (
    data_path("monolith_homekit.state")
)


# =============================================================
# MOTION CONFIG
# =============================================================

# Schlafzimmer, Küche und Flur:
# Eine Motion-Session endet nach 3 Minuten ohne neue Bewegung.
#
# Wohnzimmer:
# Ein längeres Beispielintervall verhindert neue Feed-Einträge
# bei kurzen bewegungslosen Phasen.

MOTION_TIMEOUT_NORMAL = (
    3 * 60
)

MOTION_TIMEOUT_LIVINGROOM = (
    15 * 60
)


# =============================================================
# NORMAL MONOLITH SWITCH
# =============================================================

class MonolithSwitch(Accessory):

    category = CATEGORY_SWITCH


    def __init__(
        self,
        driver,
        display_name,
        device_id,
        aid,
    ):
        super().__init__(
            driver,
            display_name,
            aid=aid,
        )


        self.device_id = (
            device_id
        )


        service = (
            self.add_preload_service(
                "Switch"
            )
        )


        self.on_characteristic = (
            service.configure_char(
                "On",
                setter_callback=
                    self.set_state,
            )
        )


    # ---------------------------------------------------------
    # STATE CHANGE FROM APPLE HOME
    # ---------------------------------------------------------

    def set_state(
        self,
        value,
    ):
        state = bool(
            value
        )


        try:
            response = requests.post(
                MONOLITH_STATE_API,

                json={
                    "device":
                        self.device_id,

                    "value":
                        state,
                },

                timeout=3,
            )


            response.raise_for_status()


            print(
                "[HOMEKIT] "
                f"{self.display_name} -> "
                f"{state}"
            )


        except requests.RequestException as error:
            print(
                "[HOMEKIT ERROR] "
                f"{self.display_name}: "
                f"{error}"
            )


# =============================================================
# MOTION TRIGGER SWITCH
# =============================================================

class MotionTriggerSwitch(Accessory):

    category = CATEGORY_SWITCH


    def __init__(
        self,
        driver,
        display_name,
        source_id,
        room,
        timeout_seconds,
        aid,
    ):
        super().__init__(
            driver,
            display_name,
            aid=aid,
        )


        self.source_id = (
            source_id
        )

        self.room = (
            room
        )

        self.timeout_seconds = (
            timeout_seconds
        )


        # Zeitpunkt der letzten Bewegung.
        self.last_motion = None


        # Ist für die aktuell laufende Motion-Session
        # bereits ein Feed-Event geschrieben worden?
        self.session_logged = False

        # Nur Laufzeitdaten; getrennt von HomeKit-Pairing und Quellcode.
        self.session_state_file = (
            data_path(f"{self.source_id}_session.json")
        )
        self.restore_motion_session()


        service = (
            self.add_preload_service(
                "Switch"
            )
        )


        self.on_characteristic = (
            service.configure_char(
                "On",
                value=False,
                setter_callback=
                    self.set_state,
            )
        )


    # ---------------------------------------------------------
    # PERSIST MOTION SESSION ACROSS SERVICE RESTARTS
    # ---------------------------------------------------------

    def restore_motion_session(self):
        try:
            data = json.loads(self.session_state_file.read_text(encoding="utf-8"))
            last_motion = data["last_motion"]
            session_logged = data["session_logged"]
            if (
                type(last_motion) not in (int, float)
                or not math.isfinite(last_motion)
                or last_motion < 0
                or type(session_logged) is not bool
            ):
                raise ValueError("Ungültiger Motion-Session-Status")
            self.last_motion = last_motion
            self.session_logged = session_logged
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"[MOTION STATE ERROR] {self.room}: {error}")

    def save_motion_session(self):
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8",
                dir=self.session_state_file.parent,
                prefix=self.session_state_file.name + ".",
                suffix=".tmp", delete=False,
            ) as handle:
                temporary_path = handle.name
                json.dump({
                    "last_motion": self.last_motion,
                    "session_logged": self.session_logged,
                }, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.session_state_file)
        except OSError as error:
            print(f"[MOTION STATE ERROR] {self.room}: {error}")
        finally:
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
                except OSError as error:
                    print(f"[MOTION STATE ERROR] {self.room}: {error}")

    # ---------------------------------------------------------
    # CREATE MOTION EVENT
    # ---------------------------------------------------------

    def create_motion_event(
        self,
    ):
        title = "Bewegung erkannt"


        response = requests.post(
            MONOLITH_EVENT_API,

            json={
                "type":
                    "motion",

                "source":
                    self.source_id,

                "room":
                    self.room,

                "title":
                    title,
            },

            timeout=3,
        )


        response.raise_for_status()


    # ---------------------------------------------------------
    # MOTION FROM APPLE HOME
    # ---------------------------------------------------------

    def set_state(
        self,
        value,
    ):
        state = bool(
            value
        )


        # AUS ist nur unser automatischer Reset.
        # Dafür soll natürlich kein Event entstehen.
        if not state:
            return


        now = time.time()


        # =====================================================
        # CHECK IF OLD SESSION EXPIRED
        # =====================================================

        if (
            self.last_motion
            is None
        ):
            new_session = True


        else:
            seconds_since_motion = (
                now
                - self.last_motion
            )


            new_session = (
                seconds_since_motion
                >= self.timeout_seconds
            )


        # Wenn genug Zeit ohne Bewegung vergangen ist,
        # beginnt jetzt eine neue Session.
        if new_session:
            self.session_logged = False


        # Jede Bewegung verlängert die aktuelle Session.
        self.last_motion = now


        # =====================================================
        # CREATE FEED EVENT
        # =====================================================

        if not self.session_logged:

            try:
                self.create_motion_event()


                self.session_logged = True


                print(
                    "[MOTION] "
                    f"{self.room} -> "
                    "neue Motion-Session"
                )


            except requests.RequestException as error:
                # Wenn MONOLITH gerade nicht erreichbar ist,
                # bleibt session_logged False.
                #
                # Dadurch versucht die nächste Bewegung
                # derselben Session erneut, den Event
                # zu speichern.
                print(
                    "[MOTION ERROR] "
                    f"{self.room}: "
                    f"{error}"
                )


        else:

            print(
                "[MOTION] "
                f"{self.room} -> "
                "Session verlängert"
            )


        # =====================================================
        # Auch Verlängerungen und fehlgeschlagene Event-Versuche speichern.
        self.save_motion_session()

        # RESET VIRTUAL SWITCH
        # =====================================================

        # Der virtuelle Schalter wird sofort wieder AUS gesetzt.
        #
        # Dadurch kann Apple Home bei der nächsten Bewegung
        # jederzeit wieder EIN senden.
        #
        # set_value() aktualisiert HomeKit direkt und löst
        # unseren setter_callback nicht erneut aus.
        self.on_characteristic.set_value(
            False
        )


# =============================================================
# BRIDGE
# =============================================================

class MonolithBridge(Bridge):

    def __init__(
        self,
        driver,
        display_name,
    ):
        super().__init__(
            driver,
            display_name,
        )


        # =====================================================
        # BEISPIELGERÄTE
        # =====================================================

        self.add_accessory(
            MonolithSwitch(
                driver,
                f"MONOLITH {devices['device_light_04']['name']}",
                "device_light_04",
                aid=2,
            )
        )


        self.add_accessory(
            MonolithSwitch(
                driver,
                f"MONOLITH {devices['device_light_01']['name']}",
                "device_light_01",
                aid=3,
            )
        )


        self.add_accessory(
            MonolithSwitch(
                driver,
                f"MONOLITH {devices['device_light_02']['name']}",
                "device_light_02",
                aid=4,
            )
        )


        self.add_accessory(
            MonolithSwitch(
                driver,
                f"MONOLITH {devices['device_light_03']['name']}",
                "device_light_03",
                aid=5,
            )
        )


        # =====================================================
        # BEISPIELGERÄTE
        # =====================================================

        self.add_accessory(
            MonolithSwitch(
                driver,
                f"MONOLITH {devices['device_light_06']['name']}",
                "device_light_06",
                aid=6,
            )
        )


        # AID 7 bleibt absichtlich frei.


        self.add_accessory(
            MonolithSwitch(
                driver,
                f"MONOLITH {devices['device_light_07']['name']}",
                "device_light_07",
                aid=8,
            )
        )


        # =====================================================
        # BEISPIELGERÄTE
        # =====================================================

        self.add_accessory(
            MonolithSwitch(
                driver,
                f"MONOLITH {devices['device_light_08']['name']}",
                "device_light_08",
                aid=9,
            )
        )


        # =====================================================
        # BEISPIELGERÄTE
        # =====================================================

        self.add_accessory(
            MonolithSwitch(
                driver,
                f"MONOLITH {devices['device_light_09']['name']}",
                "device_light_09",
                aid=10,
            )
        )


        self.add_accessory(
            MonolithSwitch(
                driver,
                f"MONOLITH {devices['device_light_10']['name']}",
                "device_light_10",
                aid=11,
            )
        )


        # =====================================================
        # BEISPIELGERÄTE
        # =====================================================

        self.add_accessory(
            MonolithSwitch(
                driver,
                f"MONOLITH {devices['device_light_11']['name']}",
                "device_light_11",
                aid=12,
            )
        )


        # =====================================================
        # AID 13
        # =====================================================

        # Bleibt absichtlich frei.
        #
        # Reserviert für zusätzliche Zubehörtypen.


        # =====================================================
        # BEISPIELGERÄTE
        # =====================================================

        self.add_accessory(
            MonolithSwitch(
                driver,
                f"MONOLITH {devices['device_light_05']['name']}",
                "device_light_05",
                aid=14,
            )
        )


        # =====================================================
        # MOTION - SCHLAFZIMMER
        # =====================================================

        self.add_accessory(
            MotionTriggerSwitch(
                driver,
                "MONOLITH Motion Schlafzimmer",
                source_id=
                    "motion_bedroom",
                room=
                    "Schlafzimmer",
                timeout_seconds=
                    MOTION_TIMEOUT_NORMAL,
                aid=15,
            )
        )


        # =====================================================
        # MOTION - KÜCHE
        # =====================================================

        self.add_accessory(
            MotionTriggerSwitch(
                driver,
                "MONOLITH Motion Küche",
                source_id=
                    "motion_kitchen",
                room=
                    "Küche",
                timeout_seconds=
                    MOTION_TIMEOUT_NORMAL,
                aid=16,
            )
        )


        # =====================================================
        # MOTION - FLUR
        # =====================================================

        self.add_accessory(
            MotionTriggerSwitch(
                driver,
                "MONOLITH Motion Flur",
                source_id=
                    "motion_hallway",
                room=
                    "Flur",
                timeout_seconds=
                    MOTION_TIMEOUT_NORMAL,
                aid=17,
            )
        )


        # =====================================================
        # MOTION - WOHNZIMMER / KAMERA
        # =====================================================

        self.add_accessory(
            MotionTriggerSwitch(
                driver,
                "MONOLITH Motion Wohnzimmer",
                source_id=
                    "motion_livingroom",
                room=
                    "Wohnzimmer",
                timeout_seconds=
                    MOTION_TIMEOUT_LIVINGROOM,
                aid=18,
            )
        )


# =============================================================
# DRIVER
# =============================================================

driver = AccessoryDriver(
    port=HOMEKIT_PORT,

    persist_file=STATE_FILE,

    pincode=HOMEKIT_PIN,
)


bridge = MonolithBridge(
    driver,
    "MONOLITH Bridge",
)


driver.add_accessory(
    accessory=bridge
)


# =============================================================
# START
# =============================================================

if __name__ == "__main__":

    print(
        "===================================="
    )

    print(
        "MONOLITH HomeKit Bridge"
    )

    print(
        "===================================="
    )

    print(
        "[HOMEKIT] Bridge gestartet"
    )

    print(
        "[HOMEKIT] Motion Trigger:"
    )

    print(
        "  Schlafzimmer -> 3 Min."
    )

    print(
        "  Küche        -> 3 Min."
    )

    print(
        "  Flur         -> 3 Min."
    )

    print(
        "  Wohnzimmer   -> 15 Min."
    )

    print(
        "===================================="
    )


    driver.start()
