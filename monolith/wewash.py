import copy
import os
import threading
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv


load_dotenv()


API_BASE_URL = "https://backend.we-wash.com"
APP_VERSION = "2.86.2"
POLL_INTERVAL_SECONDS = 30

FINAL_RESERVATION_STATUSES = {
    "EMPTY",
    "CANCELED",
    "RESERVATION_TIMED_OUT",
    "COMPLETED_SUCCESS",
    "COMPLETED_NO_CYCLE",
    "COMPLETED_WITH_ISSUE",
    "TECHNICAL_ISSUE",
}


_state_lock = threading.Lock()
_state = {
    "configured": False,
    "connected": False,
    "available_dryers": None,
    "laundry_room": None,
    "active_dryer": None,
    "updated_at": None,
    "error": None,
}


def _timestamp_to_iso(value):
    if value is None:
        return None

    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None

    if timestamp > 10_000_000_000:
        timestamp /= 1000

    try:
        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        ).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _select_laundry_room(payload):
    rooms = payload.get(
        "selectedLaundryRooms",
        [],
    )
    preferred_id = os.getenv(
        "WEWASH_LAUNDRY_ROOM_ID",
        "",
    ).strip()

    if preferred_id:
        for room in rooms:
            if room.get("id") == preferred_id:
                return room

    return rooms[0] if rooms else None


def _select_dryer_reservation(payload):
    reservations = payload.get("items", [])

    candidates = [
        reservation
        for reservation in reservations
        if (
            reservation.get("applianceType")
            == "DRYER"
            and reservation.get("status")
            not in FINAL_RESERVATION_STATUSES
        )
    ]

    if not candidates:
        return None

    priority = {
        "ACTIVE": 0,
        "PICKUP": 1,
        "PICKUP_WITH_ISSUE": 2,
        "BOOKED_READY": 3,
        "BOOKED_ACTIVATING": 4,
        "RESERVED": 5,
        "RESERVED_WAITING_FOR_CHECKOUT": 6,
        "RESERVED_WAITING_FOR_PAYMENT": 7,
        "READY": 8,
        "QUEUED": 9,
    }

    return min(
        candidates,
        key=lambda reservation: priority.get(
            reservation.get("status"),
            99,
        ),
    )


def _normalize_dryer_reservation(reservation):
    if not reservation:
        return None

    status = reservation.get("status")
    status_changed_at = _timestamp_to_iso(
        reservation.get(
            "statusChangedTimestamp"
        )
    )

    return {
        "reservation_id": reservation.get(
            "reservationId"
        ),
        "status": status,
        "running": status == "ACTIVE",
        "name": reservation.get(
            "applianceShortName"
        ),
        "status_changed_at": status_changed_at,

        # WeWash selbst zeigt bei ACTIVE nur die seit dem Start
        # verstrichene Zeit. Eine belastbare Restzeit liefert die
        # API nicht.
        "remaining_minutes": None,
        "remaining_supported": False,
    }


class WeWashClient:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "WW-App-Version": APP_VERSION,
            "WW-Client": "USERAPP",
            "User-Agent": (
                "MONOLITH Dashboard/1.0"
            ),
        })
        self.authenticated = False

    def login(self):
        response = self.session.post(
            f"{API_BASE_URL}/auth",
            json={
                "username": self.username,
                "password": self.password,
            },
            timeout=10,
        )
        response.raise_for_status()
        self.authenticated = True

    def _refresh(self):
        response = self.session.get(
            f"{API_BASE_URL}/auth/refresh",
            timeout=10,
        )
        response.raise_for_status()

    def _get(self, path):
        if not self.authenticated:
            self.login()

        response = self.session.get(
            f"{API_BASE_URL}{path}",
            timeout=10,
        )

        if response.status_code == 401:
            try:
                self._refresh()
            except requests.RequestException:
                self.login()

            response = self.session.get(
                f"{API_BASE_URL}{path}",
                timeout=10,
            )

        response.raise_for_status()
        return response.json()

    def fetch_status(self):
        laundry_rooms = self._get(
            "/v3/users/me/laundry-rooms"
        )
        reservations = self._get(
            "/v3/users/me/reservations"
        )

        room = _select_laundry_room(
            laundry_rooms
        )
        reservation = (
            _select_dryer_reservation(
                reservations
            )
        )

        availability = (
            room.get("serviceAvailability", {})
            if room
            else {}
        )

        return {
            "available_dryers": (
                availability.get(
                    "availableDryers"
                )
            ),
            "laundry_room": (
                room.get("name")
                if room
                else None
            ),
            "active_dryer": (
                _normalize_dryer_reservation(
                    reservation
                )
            ),
        }


def get_wewash_status():
    with _state_lock:
        return copy.deepcopy(_state)


def _set_state(**changes):
    with _state_lock:
        _state.update(changes)


def _monitor_loop(
    client,
    on_dryer_state_change=None,
):
    previous_running = None

    while True:
        try:
            status = client.fetch_status()
            active_dryer = status.get(
                "active_dryer"
            )
            running = bool(
                active_dryer
                and active_dryer.get("running")
            )

            _set_state(
                configured=True,
                connected=True,
                error=None,
                updated_at=(
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
                **status,
            )

            if (
                previous_running is not None
                and running != previous_running
                and on_dryer_state_change
            ):
                on_dryer_state_change(
                    running,
                    active_dryer,
                )

            previous_running = running
        except requests.RequestException as error:
            status_code = (
                error.response.status_code
                if error.response is not None
                else None
            )
            message = (
                "Anmeldung fehlgeschlagen"
                if status_code in (401, 403)
                else "WeWash nicht erreichbar"
            )
            _set_state(
                configured=True,
                connected=False,
                error=message,
            )
        except (TypeError, ValueError, KeyError):
            _set_state(
                configured=True,
                connected=False,
                error="Unerwartete WeWash-Antwort",
            )

        time.sleep(POLL_INTERVAL_SECONDS)


def start_wewash_monitor(
    on_dryer_state_change=None,
):
    username = os.getenv(
        "WEWASH_USERNAME",
        "",
    ).strip()
    password = os.getenv(
        "WEWASH_PASSWORD",
        "",
    )

    if not username or not password:
        _set_state(
            configured=False,
            connected=False,
            error="WeWash noch nicht konfiguriert",
        )
        return None

    client = WeWashClient(
        username,
        password,
    )
    thread = threading.Thread(
        target=_monitor_loop,
        args=(
            client,
            on_dryer_state_change,
        ),
        name="wewash-monitor",
        daemon=True,
    )
    thread.start()
    return thread
