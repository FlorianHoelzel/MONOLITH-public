import logging
import os
import re
import sqlite3
import time
import ctypes
import hashlib
import threading
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_from_directory,
    stream_with_context,
)
from dotenv import load_dotenv


load_dotenv()

from monolith.database import (
    acknowledge_pet_feeding_notification,
    create_meal_plan_item,
    create_pet_feeding_time,
    create_pet_shopping_item,
    create_pet_weight,
    create_package,
    create_finance_expense,
    create_finance_recurring,
    delete_package,
    delete_finance_expense,
    delete_finance_recurring,
    delete_meal_plan_item,
    delete_push_subscription,
    delete_pet_feeding_time,
    delete_pet_shopping_item,
    delete_pet_weight,
    delete_recipe_bookmark,
    get_device_states,
    get_events_since,
    get_finances,
    get_packages,
    get_latest_sensor_values,
    get_meal_plan_items,
    get_pet_data,
    get_recent_events,
    get_saved_recipes,
    get_push_subscription,
    get_sensor_history,
    get_selected_weather_location,
    get_weather_data,
    init_database,
    mark_weather_sync,
    move_meal_plan_item,
    save_device_state,
    save_event,
    save_push_subscription,
    save_recipe_bookmark,
    save_sensor_snapshot,
    save_weather_data,
    set_weather_location,
    set_pet_feeding_completed,
    set_pet_shopping_item_checked,
    set_finance_transfer,
    set_meal_plan_item_checked,
)

from monolith.weather import (
    WeatherServiceError,
    fetch_weather,
    search_locations,
)

from monolith.push_notifications import (
    PushSubscriptionGone,
    get_vapid_public_key,
    send_push_notification,
)

from monolith.package_tracking import (
    CARRIERS,
    PACKAGE_STATUSES,
    carrier_details,
    detect_carrier,
    normalize_tracking_number,
    ship24_is_configured,
    unsubscribe_ship24_tracker,
)
from monolith.package_monitor import (
    PACKAGE_URGENT_REFRESH_INTERVAL_SECONDS,
    PACKAGE_REFRESH_INTERVAL_SECONDS,
    refresh_packages,
    start_package_monitor,
)
from monolith.pet_monitor import start_pet_monitor

from monolith.devices import devices
from monolith.nintendo_switch import SWITCH_ROOM, get_switch_status, start_switch_monitor
from monolith.sensors import sensors
from monolith.system_services import (
    get_system_service_logs,
    get_system_services,
)
from monolith.raspberry_pi import get_raspberry_pi_status
from monolith.network_monitor import (
    get_network_status,
    set_network_device_flags,
    start_network_monitor,
)


init_database()

from monolith.presence import (
    get_presence_status,
    start_presence_monitor,
)

from monolith.matterbridge import (
    start_robovac_monitor,
)

from monolith.pc_status import (
    start_pc_status_monitor,
)

from monolith.lg_tv import (
    set_lg_tv_power,
    start_lg_tv_monitor,
)

from monolith.homepod import (
    start_homepod_monitor,
)

from monolith.apple_tv import (
    start_apple_tv_monitor,
)

from monolith.wewash import (
    get_wewash_status,
    start_wewash_monitor,
)

from monolith.picnic import (
    get_picnic_delivery_details,
    get_picnic_status,
    login_picnic,
    request_picnic_2fa,
    start_picnic_monitor,
    verify_picnic_2fa,
)
from monolith.icloud_planner import get_icloud_planner
from monolith.camera_stream import (
    CameraStreamBusy,
    CameraStreamUnavailable,
    get_camera_stream_status,
    open_camera_stream,
)
from monolith.recipe_api import (
    RecipeServiceError,
    fetch_random_recipe,
)


from monolith.data_paths import SOURCE_DIR

app = Flask(
    __name__,
    template_folder=str(SOURCE_DIR / "templates"),
    static_folder=str(SOURCE_DIR / "static"),
)

single_instance_mutex = None

logging.getLogger(
    "werkzeug"
).setLevel(
    logging.ERROR
)


rooms = [
    "Wohnzimmer",
    "Schlafzimmer",
    "Küche",
    "Flur",
    "Balkon",
    "Wäschekeller",
]

WEATHER_CACHE_SECONDS = 600

CAMERA_EVENT_DAYS = 7
CAMERA_EVENT_SOURCE_ID = os.getenv(
    "CAMERA_EVENT_SOURCE_ID",
    "motion_livingroom",
).strip()
CAMERA_NAME = (
    os.getenv(
        "CAMERA_NAME",
        "Kamera",
    ).strip()
    or "Kamera"
)


def acquire_single_instance():
    global single_instance_mutex

    # systemd keeps a single process on Linux. The mutex is only
    # required when MONOLITH is started manually on Windows.
    if os.name != "nt":
        return True

    kernel32 = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    )
    kernel32.CreateMutexW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_bool,
        ctypes.c_wchar_p,
    ]
    kernel32.CreateMutexW.restype = (
        ctypes.c_void_p
    )
    kernel32.CloseHandle.argtypes = [
        ctypes.c_void_p,
    ]

    handle = kernel32.CreateMutexW(
        None,
        False,
        "Local\\MONOLITH-Flask-5000",
    )

    if not handle:
        raise ctypes.WinError(
            ctypes.get_last_error()
        )

    error_already_exists = 183

    if (
        ctypes.get_last_error()
        == error_already_exists
    ):
        kernel32.CloseHandle(
            handle
        )

        return False

    single_instance_mutex = handle

    return True


def restore_latest_sensor_values():
    latest_values = (
        get_latest_sensor_values()
    )

    for room_id, values in (
        latest_values.items()
    ):
        if room_id not in sensors:
            continue

        sensors[
            room_id
        ]["temperature"] = (
            values["temperature"]
        )

        sensors[
            room_id
        ]["humidity"] = (
            values["humidity"]
        )

        if room_id == "hallway":
            sensors[room_id]["pm25"] = (
                values.get("pm25")
            )
            sensors[room_id]["iai"] = (
                values.get("iai")
            )


restore_latest_sensor_values()


ROBOVAC_EVENT_TITLES = {
    "cleaning": f"{devices['device_vacuum_01']['name']} reinigt",
    "paused": f"{devices['device_vacuum_01']['name']} pausiert",
    "returning_to_dock": (
        f"{devices['device_vacuum_01']['name']} fährt zur Station"
    ),
    "charging": f"{devices['device_vacuum_01']['name']} lädt",
    "docked": f"{devices['device_vacuum_01']['name']} ist gedockt",
}


def update_robovac_status(status):
    old_status = devices[
        "device_vacuum_01"
    ]["value"]

    if old_status == status:
        return

    devices[
        "device_vacuum_01"
    ]["value"] = status

    if (
        old_status
        in ROBOVAC_EVENT_TITLES
        and status
        in ROBOVAC_EVENT_TITLES
    ):
        save_event(
            event_type="vacuum",
            source_id=
                "device_vacuum_01",
            room=devices["device_vacuum_01"]["room"],
            title=
                ROBOVAC_EVENT_TITLES[
                    status
                ],
        )

    print(
        "[ROBOVAC] "
        f"{devices['device_vacuum_01']['room']} / {devices['device_vacuum_01']['name']} -> "
        f"{status}"
    )


def update_pc_status(status):
    device_id = "device_computer_01"
    old_value = bool(
        devices[device_id].get("value")
    )
    new_value = bool(status)

    update_standard_device(
        device_id,
        new_value,
        log_first=False,
    )

    if old_value != new_value:
        print(
            "[PC] "
            f"{devices[device_id]['room']} / {devices[device_id]['name']} -> "
            + (
                "An"
                if new_value
                else "Aus"
            )
        )


def update_lg_tv_status(status):
    device_id = "device_display_01"
    device = devices[device_id]
    old_value = device["value"]
    status_fields = (
        "value",
        "connected",
        "power_state",
        "app",
        "app_name",
        "volume",
        "muted",
    )
    old_status = tuple(
        device.get(key)
        for key in status_fields
    )
    new_value = status.get(
        "value",
        "Unbekannt",
    )
    state_key = f"device:{device_id}"

    if (
        state_key in observed_states
        and isinstance(old_value, bool)
        and isinstance(new_value, bool)
        and old_value != new_value
    ):
        save_event(
            event_type="media",
            source_id=device_id,
            room=device["room"],
            title=(
                f"{device['name']} eingeschaltet"
                if new_value
                else f"{device['name']} ausgeschaltet"
            ),
        )

    for key in status_fields:
        if key in status:
            device[key] = status[key]

    already_observed = (
        state_key in observed_states
    )
    observed_states.add(state_key)

    new_status = tuple(
        device.get(key)
        for key in status_fields
    )

    if (
        not already_observed
        or old_status != new_status
    ):
        print(
            f"[LG TV] {device['room']} / {device['name']} -> "
            f"{new_value}"
            + (
                f" · {device['app_name']}"
                if device.get("app_name")
                else ""
            )
        )


def update_homepod_status(status):
    update_apple_media_status(
        "device_speaker_01",
        status,
    )


def update_apple_tv_status(status):
    update_apple_media_status(
        "device_media_01",
        status,
    )


def update_apple_media_status(
    device_id,
    status,
):
    device = devices[device_id]
    update_media_artwork(
        device_id,
        status.get("artwork"),
    )
    new_playing = bool(
        status.get("playing", False)
    )
    state_key = (
        f"playback:{device_id}"
    )

    if device_id == "device_speaker_01":
        update_homepod_feed_state(device_id, device, status)
    else:
        update_apple_media_feed_state(
            device_id,
            device,
            status,
            new_playing,
            pause_confirm_seconds=APPLE_TV_FEED_PAUSE_CONFIRM_SECONDS,
        )

    for key in (
        "value",
        "connected",
        "playing",
        "power_state",
        "playback_state",
        "title",
        "artist",
        "album",
        "app",
        "app_name",
        "media_visible",
        "address",
        "identifier",
        "model",
        "operating_system",
        "version",
        "last_seen",
        "error",
    ):
        if key in status:
            device[key] = status[key]

    observed_states.add(state_key)


def update_homepod_feed_state(device_id, device, status):
    # Discovery/metadata failures are not evidence of a user pausing.
    if (
        not status.get("connected")
        or status.get("playback_state") not in {
            "playing", "loading", "seeking", "paused", "stopped", "idle",
        }
    ):
        state = apple_media_feed_states.get(device_id)
        if state is not None:
            state["pause_started_at"] = None
        return

    update_apple_media_feed_state(
        device_id,
        device,
        status,
        bool(status.get("playing")),
        pause_confirm_seconds=HOMEPOD_FEED_PAUSE_CONFIRM_SECONDS,
    )


def update_apple_media_feed_state(
    device_id,
    device,
    status,
    new_playing,
    pause_confirm_seconds,
):
    now = time.monotonic()
    state = apple_media_feed_states.get(device_id)

    if state is None:
        apple_media_feed_states[device_id] = {
            "active": new_playing,
            "pause_started_at": None,
        }
        return

    if new_playing:
        state["pause_started_at"] = None

        if not state["active"]:
            save_apple_media_event(
                device_id,
                device,
                playing=True,
                title=status.get("title"),
            )
            state["active"] = True

        return

    if not state["active"]:
        state["pause_started_at"] = None
        return

    power_state = str(
        status.get("power_state", "unknown")
    ).lower()

    if power_state == "off":
        save_apple_media_event(
            device_id,
            device,
            playing=False,
        )
        state["active"] = False
        state["pause_started_at"] = None
        return

    if state["pause_started_at"] is None:
        state["pause_started_at"] = now
        return

    if (
        now - state["pause_started_at"]
        < pause_confirm_seconds
    ):
        return

    save_apple_media_event(
        device_id,
        device,
        playing=False,
    )
    state["active"] = False
    state["pause_started_at"] = None


def save_apple_media_event(
    device_id,
    device,
    playing,
    title=None,
):
    save_event(
        event_type="media",
        source_id=device_id,
        room=device["room"],
        title=(
            "Wiedergabe gestartet"
            if playing
            else "Pausiert"
        ),
        detail=title if playing else None,
    )


def update_wewash_dryer_status(
    running,
    active_dryer,
):
    title = (
        f"{devices['device_dryer_01']['name']} gestartet"
        if running
        else f"{devices['device_dryer_01']['name']} ist fertig"
    )

    save_event(
        event_type="dryer",
        source_id="device_dryer_01",
        room=devices["device_dryer_01"]["room"],
        title=title,
    )

    print(
        f"[WEWASH] {devices['device_dryer_01']['room']} / "
        f"{title}"
    )


# =============================================================
# EVENT STATE
# =============================================================

observed_states = set()
apple_media_feed_states = {}
media_artwork_cache = {}
media_artwork_lock = threading.Lock()
last_sensor_snapshot_times = {}
last_air_purifier_auto_event_times = {}

SENSOR_HISTORY_INTERVAL_SECONDS = 60
APPLE_TV_FEED_PAUSE_CONFIRM_SECONDS = 180
HOMEPOD_FEED_PAUSE_CONFIRM_SECONDS = 10
AIR_PURIFIER_AUTO_EVENT_COOLDOWN_SECONDS = 15 * 60


def update_media_artwork(
    device_id,
    artwork,
):
    device = devices[device_id]
    image_bytes = (
        artwork.get("bytes")
        if isinstance(artwork, dict)
        else None
    )
    mimetype = (
        str(artwork.get("mimetype") or "")
        if isinstance(artwork, dict)
        else ""
    )

    if (
        not isinstance(image_bytes, bytes)
        or not image_bytes
        or not mimetype.startswith("image/")
    ):
        with media_artwork_lock:
            media_artwork_cache.pop(
                device_id,
                None,
            )

        device["artwork_url"] = None
        return

    token = hashlib.sha256(
        image_bytes
    ).hexdigest()[:16]

    with media_artwork_lock:
        media_artwork_cache[device_id] = {
            "bytes": image_bytes,
            "mimetype": mimetype,
            "token": token,
        }

    device["artwork_url"] = (
        f"/api/media/artwork/{device_id}?v={token}"
    )


def restore_device_states():
    stored_states = get_device_states()

    for device_id, value in stored_states.items():
        device = devices.get(device_id)

        if (
            not device
            or device.get("type")
            not in {"light", "washer"}
        ):
            continue

        device["value"] = value
        state_key = (
            "washer:in_use"
            if device.get("type") == "washer"
            else f"device:{device_id}"
        )
        observed_states.add(state_key)


restore_device_states()


# =============================================================
# HELPERS
# =============================================================

def normalize_boolean(value):
    if isinstance(
        value,
        bool,
    ):
        return value

    if isinstance(
        value,
        int,
    ):
        return value != 0

    if isinstance(
        value,
        str,
    ):
        normalized = (
            value
            .strip()
            .lower()
        )

        if normalized in [
            "true",
            "on",
            "an",
            "yes",
            "ja",
            "1",
        ]:
            return True

        if normalized in [
            "false",
            "off",
            "aus",
            "no",
            "nein",
            "0",
        ]:
            return False

    return bool(value)


def normalize_number(value):
    if isinstance(
        value,
        (int, float),
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        cleaned = (
            value
            .replace("%", "")
            .replace("°c", "")
            .replace("°C", "")
            .replace(
                "degrees",
                "",
            )
            .replace(
                "degree",
                "",
            )
            .replace(",", ".")
            .strip()
        )

        try:
            number = float(
                cleaned
            )

            if number.is_integer():
                return int(
                    number
                )

            return round(
                number,
                1,
            )

        except ValueError:
            return None

    return None


def normalize_air_purifier_mode(value):
    normalized = (
        str(value)
        .strip()
        .lower()
    )

    return {
        "auto": "Auto",
        "sleep": "Sleep",
        "medium": "Medium",
        "turbo": "Turbo",
    }.get(
        normalized,
        str(value),
    )


def air_purifier_mode_from_speed(value):
    speed = normalize_number(
        value
    )

    if speed is None:
        return None

    if speed <= 25:
        return "Sleep"

    if speed <= 60:
        return "Medium"

    return "Turbo"


def normalize_value(
    device,
    value,
):
    device_type = (
        device[
            "type"
        ]
    )

    if device_type in [
        "light",
        "switch",
    ]:
        return normalize_boolean(
            value
        )

    return value


def normalize_duration(value):
    if isinstance(
        value,
        int,
    ):
        return value

    if isinstance(
        value,
        float,
    ):
        return int(
            value
        )

    if isinstance(
        value,
        str,
    ):
        value = (
            value
            .strip()
            .lower()
        )

        value = (
            value
            .replace(
                "seconds",
                "",
            )
            .replace(
                "second",
                "",
            )
            .replace(
                "secs",
                "",
            )
            .replace(
                "sec",
                "",
            )
            .strip()
        )

        try:
            return int(
                float(
                    value
                )
            )

        except ValueError:
            return 0

    return 0


# =============================================================
# EVENT HELPERS
# =============================================================

def create_device_event(
    device_id,
    old_value,
    new_value,
):
    device = devices[
        device_id
    ]

    device_type = (
        device[
            "type"
        ]
    )

    name = device[
        "name"
    ]

    room = device[
        "room"
    ]

    if device_type in [
        "light",
        "switch",
    ]:
        if new_value:
            title = (
                f"{name} eingeschaltet"
            )

        else:
            title = (
                f"{name} ausgeschaltet"
            )

        save_event(
            event_type="device",
            source_id=device_id,
            room=room,
            title=title,
        )

        return


    if (
        device_type
        == "washer"
    ):
        if new_value:
            title = (
                f"{name} gestartet"
            )

        else:
            title = (
                f"{name} ist fertig"
            )

        save_event(
            event_type="washer",
            source_id=device_id,
            room=room,
            title=title,
        )


def update_standard_device(
    device_id,
    value,
    log_first=False,
):
    device = devices[
        device_id
    ]

    device_type = device[
        "type"
    ]

    state_key = (
        f"device:{device_id}"
    )

    normalized_value = (
        normalize_value(
            device,
            value,
        )
    )

    old_value = (
        device.get(
            "value"
        )
    )

    already_observed = (
        state_key
        in observed_states
    )

    if (
        old_value
        != normalized_value
    ):
        if (
            already_observed
            or log_first
        ):
            create_device_event(
                device_id,
                old_value,
                normalized_value,
            )

    device[
        "value"
    ] = normalized_value

    if device_type == "light":
        save_device_state(
            device_id,
            normalized_value,
        )

    observed_states.add(
        state_key
    )

    return normalized_value


# =============================================================
# SENSOR HELPERS
# =============================================================

def update_sensor(
    key,
    value,
    log_update=True,
    log_unchanged=True,
):
    sensor_map = {
        "sensor_livingroom_temperature": (
            "livingroom",
            "temperature",
        ),

        "sensor_livingroom_humidity": (
            "livingroom",
            "humidity",
        ),

        "sensor_bedroom_temperature": (
            "bedroom",
            "temperature",
        ),

        "sensor_bedroom_humidity": (
            "bedroom",
            "humidity",
        ),

        "sensor_kitchen_temperature": (
            "kitchen",
            "temperature",
        ),

        "sensor_kitchen_humidity": (
            "kitchen",
            "humidity",
        ),

        "sensor_hallway_temperature": (
            "hallway",
            "temperature",
        ),

        "sensor_hallway_humidity": (
            "hallway",
            "humidity",
        ),

        "sensor_hallway_pm25": (
            "hallway",
            "pm25",
        ),

        "sensor_hallway_iai": (
            "hallway",
            "iai",
        ),

        "sensor_bathroom_temperature": (
            "bathroom",
            "temperature",
        ),

        "sensor_bathroom_humidity": (
            "bathroom",
            "humidity",
        ),

        "sensor_balcony_temperature": (
            "balcony",
            "temperature",
        ),

        "sensor_balcony_humidity": (
            "balcony",
            "humidity",
        ),
    }

    if key not in sensor_map:
        return None

    room_id, sensor_type = (
        sensor_map[
            key
        ]
    )

    normalized_value = (
        normalize_number(
            value
        )
    )

    if normalized_value is None:
        print(
            f"[INVALID SENSOR] "
            f"{key} -> {value!r}; "
            "vorheriger Wert bleibt erhalten"
        )

        return None

    old_value = sensors[
        room_id
    ].get(
        sensor_type
    )

    sensors[
        room_id
    ][
        sensor_type
    ] = normalized_value

    if (
        log_update
        and (
            log_unchanged
            or old_value != normalized_value
        )
    ):
        print(
            f"[{key}] "
            f"{sensors[room_id]['name']} / "
            f"{sensor_type} -> "
            f"{normalized_value}"
        )

    return (
        room_id,
        sensor_type,
    )


# =============================================================
# DASHBOARD
# =============================================================

@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        devices=devices,
        rooms=rooms,
        sensors=sensors,
    )


@app.route("/design-lab")
def design_lab():
    return render_template(
        "design_lab.html",
        devices=devices,
        rooms=rooms,
    )


# =============================================================
# API - DEVICES
# =============================================================

@app.route(
    "/api/devices"
)
def get_devices():
    switch_device = devices["device_console_01"]
    switch_device.update(get_switch_status())
    switch_device["room"] = SWITCH_ROOM
    wewash_status = get_wewash_status()
    wewash_device = devices[
        "device_dryer_01"
    ]

    for key in (
        "configured",
        "connected",
        "available_dryers",
        "active_dryer",
    ):
        wewash_device[key] = (
            wewash_status.get(key)
        )

    active_dryer = wewash_status.get(
        "active_dryer"
    )

    if not wewash_status.get("configured"):
        wewash_device["value"] = "unknown"
    elif not wewash_status.get("connected"):
        wewash_device["value"] = "unavailable"
    elif active_dryer:
        wewash_device["value"] = (
            active_dryer.get("status", "reserved")
        )
    else:
        wewash_device["value"] = "idle"

    return jsonify(
        devices
    )


@app.route(
    "/api/media/artwork/<device_id>"
)
def get_media_artwork(device_id):
    device = devices.get(device_id)

    if (
        not device
        or device.get("type") != "media"
    ):
        return "", 404

    with media_artwork_lock:
        cached = media_artwork_cache.get(
            device_id
        )

    if not cached:
        return "", 404

    response = Response(
        cached["bytes"],
        mimetype=cached["mimetype"],
    )
    response.cache_control.private = True
    response.cache_control.max_age = 300
    response.set_etag(
        cached["token"]
    )

    return response.make_conditional(
        request
    )


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(
        app.static_folder,
        "service-worker.js",
        mimetype="application/javascript",
    )
    response.headers[
        "Cache-Control"
    ] = "no-cache, no-store, must-revalidate"
    response.headers[
        "Service-Worker-Allowed"
    ] = "/"
    return response


# =============================================================
# API - SYSTEM SERVICES
# =============================================================

@app.route(
    "/api/system/services"
)
def get_services_status():
    return jsonify(
        get_system_services()
    )


@app.route(
    "/api/system/services/logs"
)
def get_services_logs():
    result = get_system_service_logs(
        cursor=request.args.get("cursor")
    )

    return jsonify(result), (
        200
        if result.get("success")
        else 503
    )


@app.route(
    "/api/system/raspberry-pi"
)
def get_raspberry_pi_metrics():
    return jsonify(
        get_raspberry_pi_status()
    )


# =============================================================
# API - NETWORK
# =============================================================

@app.route("/api/system/network")
def get_network_metrics():
    force = request.args.get("refresh", "").lower() in {
        "1", "true", "yes",
    }
    result = get_network_status(force=force)
    return jsonify(result), (200 if result.get("success") else 503)


@app.route(
    "/api/system/network/devices/<path:mac>",
    methods=["PATCH"],
)
def update_network_device(mac):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "error": "Ungültige Anfrage.",
        }), 400

    allowed = {"known", "important"}
    if not allowed.intersection(payload):
        return jsonify({
            "success": False,
            "error": "Keine unterstützte Änderung angegeben.",
        }), 400

    for key in allowed.intersection(payload):
        if not isinstance(payload[key], bool):
            return jsonify({
                "success": False,
                "error": f"{key} muss ein Wahrheitswert sein.",
            }), 400

    updated = set_network_device_flags(
        mac,
        is_known=payload.get("known"),
        is_important=payload.get("important"),
    )
    if not updated:
        return jsonify({
            "success": False,
            "error": "Netzwerkgerät nicht gefunden.",
        }), 404

    return jsonify({
        "success": True,
        "device": {
            "mac": updated["mac"],
            "known": bool(updated["is_known"]),
            "important": bool(updated["is_important"]),
        },
    })


# =============================================================
# API - WEB PUSH
# =============================================================


def normalize_push_subscription(data):
    if not isinstance(data, dict):
        return None

    endpoint = str(
        data.get("endpoint", "")
    ).strip()
    keys = data.get("keys")

    if not isinstance(keys, dict):
        return None

    p256dh = str(
        keys.get("p256dh", "")
    ).strip()
    auth = str(
        keys.get("auth", "")
    ).strip()
    parsed_endpoint = urlparse(endpoint)

    if (
        parsed_endpoint.scheme != "https"
        or not parsed_endpoint.netloc
        or not p256dh
        or not auth
        or len(endpoint) > 4096
        or len(p256dh) > 512
        or len(auth) > 256
    ):
        return None

    return {
        "endpoint": endpoint,
        "keys": {
            "p256dh": p256dh,
            "auth": auth,
        },
    }


@app.route("/api/push/public-key")
def get_push_public_key():
    return jsonify({
        "public_key": get_vapid_public_key(),
    })


@app.route(
    "/api/push/subscribe",
    methods=["POST"],
)
def subscribe_push():
    data = request.get_json(silent=True)
    subscription = normalize_push_subscription(data)

    if subscription is None:
        return jsonify({
            "success": False,
            "error": "Ungültiges Push-Abonnement",
        }), 400

    previous_endpoint = str(data.get("previous_endpoint") or "").strip()
    previous_url = urlparse(previous_endpoint)
    if previous_endpoint and (
        previous_url.scheme != "https"
        or not previous_url.netloc
        or len(previous_endpoint) > 4096
    ):
        return jsonify({"success": False, "error": "Ungültiger alter Push-Endpunkt"}), 400

    save_push_subscription(
        subscription["endpoint"],
        subscription["keys"]["p256dh"],
        subscription["keys"]["auth"],
        request.user_agent.string[:500],
        previous_endpoint=previous_endpoint,
    )
    return jsonify({
        "success": True,
    })


@app.route(
    "/api/push/status",
    methods=["POST"],
)
def get_push_status():
    data = request.get_json(silent=True) or {}
    endpoint = str(
        data.get("endpoint", "")
    ).strip()
    parsed_endpoint = urlparse(endpoint)

    if (
        parsed_endpoint.scheme != "https"
        or not parsed_endpoint.netloc
        or len(endpoint) > 4096
    ):
        return jsonify({
            "success": False,
            "error": "Ungültiger Push-Endpunkt",
        }), 400

    return jsonify({
        "success": True,
        "subscribed": get_push_subscription(
            endpoint
        ) is not None,
    })


@app.route(
    "/api/push/ack",
    methods=["POST"],
)
def acknowledge_push_notification():
    data = request.get_json(silent=True) or {}
    message_id = str(
        data.get("message_id", "")
    ).strip()
    match = re.fullmatch(
        r"pet:(\d{4}-\d{2}-\d{2}):(\d+)",
        message_id,
    )

    if match is None:
        return jsonify({
            "success": False,
            "error": "Ungültige Nachrichten-ID",
        }), 400

    acknowledged = acknowledge_pet_feeding_notification(
        int(match.group(2)),
        match.group(1),
    )
    return jsonify({
        "success": acknowledged,
    }), 200 if acknowledged else 404


@app.route(
    "/api/push/unsubscribe",
    methods=["POST"],
)
def unsubscribe_push():
    data = request.get_json(silent=True) or {}
    endpoint = str(
        data.get("endpoint", "")
    ).strip()

    if endpoint:
        delete_push_subscription(endpoint)

    return jsonify({
        "success": True,
    })


@app.route(
    "/api/push/test",
    methods=["POST"],
)
def test_push():
    data = request.get_json(silent=True) or {}
    endpoint = str(
        data.get("endpoint", "")
    ).strip()
    subscription = get_push_subscription(endpoint)

    if subscription is None:
        return jsonify({
            "success": False,
            "error": "Push-Abonnement nicht gefunden",
        }), 404

    try:
        send_push_notification(
            subscription,
            "MONOLITH",
            "Benachrichtigungen sind aktiviert.",
            url="/",
            tag="monolith-test",
        )
    except PushSubscriptionGone:
        delete_push_subscription(endpoint)
        return jsonify({
            "success": False,
            "error": "Push-Abonnement ist nicht mehr gültig",
        }), 410
    except Exception:
        app.logger.exception(
            "Test-Push konnte nicht gesendet werden"
        )
        return jsonify({
            "success": False,
            "error": "Testbenachrichtigung konnte nicht gesendet werden",
        }), 502

    return jsonify({
        "success": True,
    })


@app.route(
    "/api/state",
    methods=[
        "POST",
    ],
)
def update_state():
    data = (
        request.get_json()
    )

    if not data:
        return jsonify({
            "success": False,
            "error":
                "No JSON data received",
        }), 400

    device_id = (
        data.get(
            "device"
        )
    )

    value = (
        data.get(
            "value"
        )
    )

    if (
        device_id
        not in devices
    ):
        return jsonify({
            "success": False,
            "error":
                "Unknown device",
        }), 404

    if devices[device_id].get(
        "read_only",
        False,
    ):
        return jsonify({
            "success": False,
            "error":
                "Device is read-only",
        }), 403

    if device_id == "device_display_01":
        requested_value = normalize_boolean(
            value
        )

        try:
            result = set_lg_tv_power(
                requested_value
            )
        except RuntimeError as error:
            return jsonify({
                "success": False,
                "error": str(error),
            }), 503

        return jsonify({
            "device": device_id,
            "value": requested_value,
            **result,
        })

    value = (
        update_standard_device(
            device_id,
            value,
            log_first=True,
        )
    )

    device = devices[
        device_id
    ]

    print(
        f"[LIVE] "
        f"{device['room']} / "
        f"{device['name']} -> "
        f"{value}"
    )

    return jsonify({
        "success": True,
        "device": device_id,
        "value": value,
    })


# =============================================================
# API - SENSORS
# =============================================================

@app.route(
    "/api/sensors"
)
def get_sensors():
    return jsonify(
        sensors
    )


@app.route(
    "/api/history"
)
def get_history():
    room_id = (
        request.args.get(
            "room",
            "livingroom",
        )
    )

    try:
        hours = int(
            request.args.get(
                "hours",
                24,
            )
        )

    except ValueError:
        hours = 24

    if room_id not in sensors:
        return jsonify({
            "success": False,
            "error":
                "Unknown room",
        }), 404

    if hours not in [
        24,
        168,
    ]:
        hours = 24

    history = (
        get_sensor_history(
            room_id,
            hours,
        )
    )

    return jsonify({
        "success": True,
        "room": room_id,
        "room_name":
            sensors[
                room_id
            ]["name"],
        "hours": hours,
        "history": history,
    })


# =============================================================
# API - WEATHER
# =============================================================


def serialize_weather_location(location):
    return {
        "id": location["id"],
        "provider_location_id": location["provider_location_id"],
        "geocoding_provider": location.get("geocoding_provider") or "open_meteo",
        "postal_code": location.get("postal_code") or "",
        "name": location["name"],
        "city": location.get("city") or location["name"],
        "admin1": location.get("admin1") or "",
        "country": location.get("country") or "",
        "country_code": location.get("country_code") or "",
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "elevation": location.get("elevation"),
        "timezone": location["timezone"],
    }


def weather_dashboard_payload(force_refresh=False):
    location = get_selected_weather_location()
    if location is None:
        return {
            "success": True,
            "configured": False,
        }, 200

    if (
        location.get("geocoding_provider") == "nominatim"
        and location.get("postal_code")
        and not location.get("city")
    ):
        try:
            refreshed_locations = search_locations(location["postal_code"])
            if refreshed_locations:
                location = set_weather_location(refreshed_locations[0])
        except WeatherServiceError:
            pass

    cached = get_weather_data(location["id"])
    last_synced_at = location.get("last_synced_at")
    cache_is_fresh = (
        last_synced_at is not None
        and int(time.time()) - int(last_synced_at) < WEATHER_CACHE_SECONDS
        and cached.get("current") is not None
    )
    warning = None
    stale = False

    if force_refresh or not cache_is_fresh:
        try:
            fresh_data = fetch_weather(
                location["latitude"],
                location["longitude"],
                location["timezone"],
            )
            save_weather_data(location["id"], fresh_data)
            cached = get_weather_data(location["id"])
            last_synced_at = int(time.time())
        except WeatherServiceError as error:
            warning = str(error)
            mark_weather_sync(location["id"], warning)
            stale = cached.get("current") is not None
            if not stale:
                return {
                    "success": False,
                    "configured": True,
                    "location": serialize_weather_location(location),
                    "error": warning,
                }, 502

    return {
        "success": True,
        "configured": True,
        "location": serialize_weather_location(location),
        "current": cached["current"],
        "hourly": cached["hourly"],
        "daily": cached["daily"],
        "updated_at": last_synced_at,
        "stale": stale,
        "warning": warning,
        "attribution": {
            "label": "Wetterdaten von Open-Meteo",
            "url": "https://open-meteo.com/",
        },
    }, 200


@app.route("/api/weather/locations")
def get_weather_locations():
    query = str(request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({
            "success": True,
            "locations": [],
        })
    try:
        locations = search_locations(query)
    except WeatherServiceError as error:
        return jsonify({
            "success": False,
            "error": str(error),
        }), 502
    return jsonify({
        "success": True,
        "locations": locations,
    })


@app.route("/api/weather/location", methods=["POST"])
def select_weather_location():
    data = request.get_json(silent=True) or {}
    try:
        provider_location_id = int(data.get("provider_location_id"))
        latitude = float(data.get("latitude"))
        longitude = float(data.get("longitude"))
        elevation = data.get("elevation")
        elevation = float(elevation) if elevation is not None else None
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "error": "Der ausgewählte Ort ist ungültig.",
        }), 400

    name = str(data.get("name") or "").strip()[:120]
    timezone = str(data.get("timezone") or "auto").strip()[:80]
    postal_code = str(data.get("postal_code") or "").strip()
    geocoding_provider = str(
        data.get("geocoding_provider") or "open_meteo"
    ).strip()
    if (
        provider_location_id <= 0
        or not name
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
        or not timezone
        or (postal_code and (len(postal_code) != 5 or not postal_code.isdigit()))
        or geocoding_provider not in {"open_meteo", "nominatim"}
    ):
        return jsonify({
            "success": False,
            "error": "Der ausgewählte Ort ist ungültig.",
        }), 400

    location = set_weather_location({
        "provider_location_id": provider_location_id,
        "geocoding_provider": geocoding_provider,
        "postal_code": postal_code,
        "name": name,
        "city": str(data.get("city") or name).strip()[:120],
        "admin1": str(data.get("admin1") or "").strip()[:120],
        "country": str(data.get("country") or "").strip()[:120],
        "country_code": str(data.get("country_code") or "").strip()[:4],
        "latitude": latitude,
        "longitude": longitude,
        "elevation": elevation,
        "timezone": timezone,
    })
    payload, status = weather_dashboard_payload(force_refresh=True)
    payload["location"] = serialize_weather_location(location)
    return jsonify(payload), status


@app.route("/api/weather")
def get_weather():
    force_refresh = str(request.args.get("refresh") or "").lower() in {
        "1",
        "true",
        "yes",
    }
    payload, status = weather_dashboard_payload(force_refresh)
    return jsonify(payload), status


# =============================================================
# API - PRESENCE
# =============================================================

@app.route(
    "/api/presence"
)
def get_presence():
    status = (
        get_presence_status()
    )

    return jsonify({
        "success": True,
        **status,
    })


# =============================================================
# API - WEWASH
# =============================================================

@app.route(
    "/api/wewash"
)
def get_wewash():
    return jsonify({
        "success": True,
        **get_wewash_status(),
    })


# =============================================================
# API - PICNIC
# =============================================================

@app.route(
    "/api/picnic"
)
def get_picnic():
    return jsonify(
        get_picnic_status(
            force_refresh=(
                request.args.get("refresh")
                == "1"
            )
        )
    )


@app.route(
    "/api/picnic/deliveries/<delivery_id>"
)
def get_picnic_delivery(delivery_id):
    result = get_picnic_delivery_details(
        delivery_id
    )

    return jsonify(result), (
        200
        if result.get("success")
        else 503
    )


@app.route(
    "/api/picnic/login",
    methods=[
        "POST",
    ],
)
def authenticate_picnic():
    data = request.get_json(
        silent=True
    ) or {}

    result = login_picnic(
        username=data.get("username"),
        password=data.get("password"),
        country_code=data.get(
            "country_code",
            "DE",
        ),
    )

    return jsonify(result), (
        200
        if result.get("success")
        else 401
    )


@app.route(
    "/api/picnic/2fa/request",
    methods=[
        "POST",
    ],
)
def generate_picnic_2fa():
    result = request_picnic_2fa()

    return jsonify(result), (
        200
        if result.get("success")
        else 503
    )


@app.route(
    "/api/picnic/2fa/verify",
    methods=[
        "POST",
    ],
)
def confirm_picnic_2fa():
    data = request.get_json(
        silent=True
    ) or {}

    result = verify_picnic_2fa(
        data.get("code")
    )

    return jsonify(result), (
        200
        if result.get("success")
        else 400
    )


# =============================================================
# API - PLANNER
# =============================================================

@app.route(
    "/api/planner"
)
def get_planner():
    today = date.today()

    try:
        start_date = date.fromisoformat(
            request.args.get(
                "start",
                today.isoformat(),
            )
        )
        end_date = date.fromisoformat(
            request.args.get(
                "end",
                (today + timedelta(days=42)).isoformat(),
            )
        )
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "error": "Ungültiger Datumsbereich",
        }), 400

    try:
        result = get_icloud_planner(
            start_date,
            end_date,
            force_refresh=(
                request.args.get("refresh") == "1"
            ),
        )
    except ValueError:
        return jsonify({
            "success": False,
            "error": "Ungültiger Datumsbereich",
        }), 400

    return jsonify(result), (
        200
        if result.get("success")
        else 503
    )


# =============================================================
# API - MEAL PLAN
# =============================================================


def meal_plan_week_starts():
    today = date.today()
    current = today - timedelta(days=today.weekday())
    return current, current + timedelta(days=7)


def validate_meal_plan_name(value):
    if not isinstance(value, str):
        return None

    name = value.strip()
    if not name or len(name) > 120:
        return None

    return name


@app.route("/api/meal-plan")
def get_meal_plan():
    current_start, next_start = meal_plan_week_starts()
    items = get_meal_plan_items((
        current_start.isoformat(),
        next_start.isoformat(),
    ))

    return jsonify({
        "success": True,
        "weeks": [
            {
                "offset": 0,
                "start": current_start.isoformat(),
                "items": [
                    item
                    for item in items
                    if (
                        item["week_start"] == current_start.isoformat()
                        and not item["checked"]
                    )
                ],
            },
            {
                "offset": 1,
                "start": next_start.isoformat(),
                "items": [
                    item
                    for item in items
                    if (
                        item["week_start"] == next_start.isoformat()
                        and not item["checked"]
                    )
                ],
            },
        ],
    })


@app.route(
    "/api/meal-plan/items",
    methods=["POST"],
)
def add_meal_plan_item():
    data = request.get_json(silent=True) or {}
    name = validate_meal_plan_name(data.get("name"))
    week_offset = data.get("week_offset")

    if name is None:
        return jsonify({
            "success": False,
            "error": "Bitte ein Gericht mit höchstens 120 Zeichen eingeben",
        }), 400

    if week_offset not in (0, 1):
        return jsonify({
            "success": False,
            "error": "Ungültige Kalenderwoche",
        }), 400

    week_start = meal_plan_week_starts()[week_offset].isoformat()
    entry_id = create_meal_plan_item(week_start, name)
    return jsonify({
        "success": True,
        "entry_id": entry_id,
    }), 201


@app.route(
    "/api/meal-plan/items/<int:entry_id>",
    methods=["PUT"],
)
def update_meal_plan_item(entry_id):
    data = request.get_json(silent=True) or {}
    checked = data.get("checked")
    week_offset = data.get("week_offset")

    if isinstance(checked, bool):
        updated = set_meal_plan_item_checked(entry_id, checked)
    elif week_offset in (0, 1):
        week_start = meal_plan_week_starts()[week_offset].isoformat()
        updated = move_meal_plan_item(entry_id, week_start)
    else:
        return jsonify({
            "success": False,
            "error": "Ungültige Änderung",
        }), 400

    if not updated:
        return jsonify({
            "success": False,
            "error": "Gericht nicht gefunden",
        }), 404

    return jsonify({"success": True})


@app.route(
    "/api/meal-plan/items/<int:entry_id>",
    methods=["DELETE"],
)
def remove_meal_plan_item(entry_id):
    if not delete_meal_plan_item(entry_id):
        return jsonify({
            "success": False,
            "error": "Gericht nicht gefunden",
        }), 404

    return jsonify({"success": True})


@app.route("/api/meal-plan/random-recipe")
def get_random_recipe():
    try:
        recipe = fetch_random_recipe()
    except RecipeServiceError as error:
        return jsonify({
            "success": False,
            "error": str(error),
        }), 503

    return jsonify({
        "success": True,
        "recipe": recipe,
    })


def validate_recipe_bookmark(value):
    if not isinstance(value, dict):
        return None

    source_id = str(value.get("source_id") or value.get("id") or "").strip()
    title = validate_meal_plan_name(value.get("title"))
    instructions = value.get("instructions")
    ingredients = value.get("ingredients")

    if (
        not source_id
        or len(source_id) > 100
        or title is None
        or not isinstance(instructions, str)
        or not instructions.strip()
        or len(instructions) > 20000
        or not isinstance(ingredients, list)
        or len(ingredients) > 80
    ):
        return None

    normalized_ingredients = []
    for ingredient in ingredients:
        if not isinstance(ingredient, dict):
            return None

        name = str(ingredient.get("name") or "").strip()
        measure = str(ingredient.get("measure") or "").strip()
        if not name or len(name) > 300 or len(measure) > 120:
            return None

        normalized_ingredients.append({
            "name": name,
            "measure": measure,
        })

    def external_url(raw_value):
        candidate = str(raw_value or "")[:1000].strip()
        parsed = urlparse(candidate)
        if parsed.scheme == "https" and parsed.netloc:
            return candidate
        return ""

    return {
        "id": source_id,
        "source_id": source_id,
        "title": title,
        "category": str(value.get("category") or "")[:100].strip(),
        "area": str(value.get("area") or "")[:100].strip(),
        "image_url": external_url(value.get("image_url")),
        "instructions": instructions.strip(),
        "source_url": external_url(value.get("source_url")),
        "video_url": external_url(value.get("video_url")),
        "ingredients": normalized_ingredients,
    }


@app.route("/api/meal-plan/bookmarks")
def get_recipe_bookmarks():
    return jsonify({
        "success": True,
        "recipes": get_saved_recipes(),
    })


@app.route(
    "/api/meal-plan/bookmarks",
    methods=["POST"],
)
def add_recipe_bookmark():
    data = request.get_json(silent=True) or {}
    recipe = validate_recipe_bookmark(data.get("recipe"))

    if recipe is None:
        return jsonify({
            "success": False,
            "error": "Das Rezept konnte nicht gespeichert werden",
        }), 400

    bookmark_id = save_recipe_bookmark(
        recipe["source_id"],
        recipe["title"],
        recipe,
    )
    return jsonify({
        "success": True,
        "bookmark_id": bookmark_id,
    }), 201


@app.route(
    "/api/meal-plan/bookmarks/<int:bookmark_id>",
    methods=["DELETE"],
)
def remove_recipe_bookmark(bookmark_id):
    if not delete_recipe_bookmark(bookmark_id):
        return jsonify({
            "success": False,
            "error": "Gespeichertes Rezept nicht gefunden",
        }), 404

    return jsonify({"success": True})


# =============================================================
# API - PET
# =============================================================


def validate_pet_text(value, maximum_length=80):
    if not isinstance(value, str):
        return None

    text = value.strip()

    if not text or len(text) > maximum_length:
        return None

    return text


def validate_pet_time(value):
    if not isinstance(value, str):
        return None

    try:
        return datetime.strptime(value, "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


@app.route("/api/pet")
def get_pet_entries():
    today = date.today().isoformat()
    return jsonify({
        "success": True,
        "date": today,
        **get_pet_data(today),
    })


@app.route(
    "/api/pet/feedings",
    methods=["POST"],
)
def add_pet_feeding():
    data = request.get_json(silent=True) or {}
    label = validate_pet_text(data.get("label"), 60)
    time_of_day = validate_pet_time(data.get("time_of_day"))

    if label is None:
        return jsonify({
            "success": False,
            "error": "Bitte eine Bezeichnung eingeben",
        }), 400

    if time_of_day is None:
        return jsonify({
            "success": False,
            "error": "Bitte eine gültige Uhrzeit eingeben",
        }), 400

    entry_id = create_pet_feeding_time(label, time_of_day)
    return jsonify({
        "success": True,
        "entry_id": entry_id,
    }), 201


@app.route(
    "/api/pet/feedings/<int:entry_id>/completion",
    methods=["PUT"],
)
def update_pet_feeding_completion(entry_id):
    data = request.get_json(silent=True) or {}
    completed = data.get("completed")

    if not isinstance(completed, bool):
        return jsonify({
            "success": False,
            "error": "Ungültiger Erledigt-Status",
        }), 400

    if not set_pet_feeding_completed(
        entry_id,
        date.today().isoformat(),
        completed,
    ):
        return jsonify({
            "success": False,
            "error": "Futterzeit nicht gefunden",
        }), 404

    return jsonify({"success": True})


@app.route(
    "/api/pet/feedings/<int:entry_id>",
    methods=["DELETE"],
)
def remove_pet_feeding(entry_id):
    if not delete_pet_feeding_time(entry_id):
        return jsonify({
            "success": False,
            "error": "Futterzeit nicht gefunden",
        }), 404

    return jsonify({"success": True})


@app.route(
    "/api/pet/weights",
    methods=["POST"],
)
def add_pet_weight():
    data = request.get_json(silent=True) or {}

    try:
        weight_kg = Decimal(
            str(data.get("weight_kg", "")).replace(",", ".")
        )
        weight_grams = int(weight_kg * 1000)
    except (InvalidOperation, OverflowError, TypeError, ValueError):
        weight_grams = 0

    try:
        recorded_on = date.fromisoformat(
            data.get("recorded_on", "")
        ).isoformat()
    except (TypeError, ValueError):
        recorded_on = None

    if not 100 <= weight_grams <= 100000:
        return jsonify({
            "success": False,
            "error": "Bitte ein gültiges Gewicht eingeben",
        }), 400

    if recorded_on is None:
        return jsonify({
            "success": False,
            "error": "Bitte ein gültiges Datum auswählen",
        }), 400

    entry_id = create_pet_weight(weight_grams, recorded_on)
    return jsonify({
        "success": True,
        "entry_id": entry_id,
    }), 201


@app.route(
    "/api/pet/weights/<int:entry_id>",
    methods=["DELETE"],
)
def remove_pet_weight(entry_id):
    if not delete_pet_weight(entry_id):
        return jsonify({
            "success": False,
            "error": "Gewichtseintrag nicht gefunden",
        }), 404

    return jsonify({"success": True})


@app.route(
    "/api/pet/shopping",
    methods=["POST"],
)
def add_pet_shopping_item():
    data = request.get_json(silent=True) or {}
    name = validate_pet_text(data.get("name"), 100)

    if name is None:
        return jsonify({
            "success": False,
            "error": "Bitte einen Artikel eingeben",
        }), 400

    entry_id = create_pet_shopping_item(name)
    return jsonify({
        "success": True,
        "entry_id": entry_id,
    }), 201


@app.route(
    "/api/pet/shopping/<int:entry_id>",
    methods=["PUT"],
)
def update_pet_shopping_item(entry_id):
    data = request.get_json(silent=True) or {}
    checked = data.get("checked")

    if not isinstance(checked, bool):
        return jsonify({
            "success": False,
            "error": "Ungültiger Erledigt-Status",
        }), 400

    if not set_pet_shopping_item_checked(entry_id, checked):
        return jsonify({
            "success": False,
            "error": "Artikel nicht gefunden",
        }), 404

    return jsonify({"success": True})


@app.route(
    "/api/pet/shopping/<int:entry_id>",
    methods=["DELETE"],
)
def remove_pet_shopping_item(entry_id):
    if not delete_pet_shopping_item(entry_id):
        return jsonify({
            "success": False,
            "error": "Artikel nicht gefunden",
        }), 404

    return jsonify({"success": True})


# =============================================================
# API - FINANCES
# =============================================================


def parse_finance_amount(value, allow_zero=False):
    try:
        amount = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None

    if (
        not amount.is_finite()
        or amount < 0
        or (amount == 0 and not allow_zero)
    ):
        return None

    cents = amount * 100

    if cents != cents.to_integral_value():
        return None

    return int(cents)


def validate_finance_name(value):
    if not isinstance(value, str):
        return None

    name = value.strip()

    if not name or len(name) > 80:
        return None

    return name


def validate_finance_month(value):
    if not isinstance(value, str):
        return None

    try:
        parsed_month = date.fromisoformat(f"{value}-01")
    except ValueError:
        return None

    return parsed_month.strftime("%Y-%m")


@app.route("/api/finances")
def get_finance_entries():
    month = validate_finance_month(
        request.args.get(
            "month",
            date.today().strftime("%Y-%m"),
        )
    )

    if month is None:
        return jsonify({
            "success": False,
            "error": "Ungültiger Monat",
        }), 400

    return jsonify({
        "success": True,
        **get_finances(month),
    })


@app.route(
    "/api/finances/transfer",
    methods=["PUT"],
)
def update_finance_transfer():
    data = request.get_json(silent=True) or {}
    month = validate_finance_month(data.get("month"))
    amount_cents = parse_finance_amount(
        data.get("amount"),
        allow_zero=True,
    )

    if month is None:
        return jsonify({
            "success": False,
            "error": "Ungültiger Monat",
        }), 400

    if amount_cents is None:
        return jsonify({
            "success": False,
            "error": "Bitte einen gültigen Übertrag eingeben",
        }), 400

    set_finance_transfer(month, amount_cents)

    return jsonify({"success": True})


@app.route(
    "/api/finances/recurring",
    methods=["POST"],
)
def add_finance_recurring():
    data = request.get_json(silent=True) or {}
    entry_type = data.get("entry_type")
    name = validate_finance_name(data.get("name"))
    amount_cents = parse_finance_amount(data.get("amount"))
    start_month = validate_finance_month(
        data.get(
            "start_month",
            date.today().strftime("%Y-%m"),
        )
    )

    if entry_type not in ("income", "fixed_expense"):
        return jsonify({
            "success": False,
            "error": "Ungültige Kategorie",
        }), 400

    if name is None:
        return jsonify({
            "success": False,
            "error": "Bitte eine Bezeichnung eingeben",
        }), 400

    if amount_cents is None:
        return jsonify({
            "success": False,
            "error": "Bitte einen gültigen Betrag eingeben",
        }), 400

    if start_month is None:
        return jsonify({
            "success": False,
            "error": "Ungültiger Startmonat",
        }), 400

    entry_id = create_finance_recurring(
        entry_type,
        name,
        amount_cents,
        start_month,
    )

    return jsonify({
        "success": True,
        "entry_id": entry_id,
    }), 201


@app.route(
    "/api/finances/recurring/<int:entry_id>",
    methods=["DELETE"],
)
def remove_finance_recurring(entry_id):
    effective_month = validate_finance_month(
        request.args.get(
            "month",
            date.today().strftime("%Y-%m"),
        )
    )

    if effective_month is None:
        return jsonify({
            "success": False,
            "error": "Ungültiger Monat",
        }), 400

    if not delete_finance_recurring(entry_id, effective_month):
        return jsonify({
            "success": False,
            "error": "Eintrag nicht gefunden",
        }), 404

    return jsonify({"success": True})


@app.route(
    "/api/finances/expenses",
    methods=["POST"],
)
def add_finance_expense():
    data = request.get_json(silent=True) or {}
    name = validate_finance_name(data.get("name"))
    amount_cents = parse_finance_amount(data.get("amount"))

    try:
        spent_on = date.fromisoformat(
            data.get("spent_on", "")
        ).isoformat()
    except (TypeError, ValueError):
        spent_on = None

    if name is None:
        return jsonify({
            "success": False,
            "error": "Bitte eine Bezeichnung eingeben",
        }), 400

    if amount_cents is None:
        return jsonify({
            "success": False,
            "error": "Bitte einen gültigen Betrag eingeben",
        }), 400

    if spent_on is None:
        return jsonify({
            "success": False,
            "error": "Bitte ein gültiges Datum auswählen",
        }), 400

    entry_id = create_finance_expense(
        name,
        amount_cents,
        spent_on,
    )

    return jsonify({
        "success": True,
        "entry_id": entry_id,
    }), 201


@app.route(
    "/api/finances/expenses/<int:entry_id>",
    methods=["DELETE"],
)
def remove_finance_expense(entry_id):
    if not delete_finance_expense(entry_id):
        return jsonify({
            "success": False,
            "error": "Eintrag nicht gefunden",
        }), 404

    return jsonify({"success": True})


# =============================================================
# API - PACKAGES
# =============================================================


def validate_package_text(value, maximum_length, required=False):
    if value is None and not required:
        return None

    if not isinstance(value, str):
        return None

    text = value.strip()

    if required and not text:
        return None

    if len(text) > maximum_length:
        return None

    return text or None


def validate_package_date(value):
    if value in (None, ""):
        return None

    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        return False


def serialize_package(package):
    result = dict(package)
    result["carrier_details"] = carrier_details(
        package["carrier"],
        package["tracking_number"],
    )
    result["status_label"] = PACKAGE_STATUSES.get(
        package["status"],
        package["status"],
    )

    for history_item in result.get("history", []):
        history_item["status_label"] = PACKAGE_STATUSES.get(
            history_item["status"],
            history_item["status"],
        )

    return result


@app.route("/api/packages")
def get_package_entries():
    return jsonify({
        "success": True,
        "tracking_configured": ship24_is_configured(),
        "refresh_interval_seconds": PACKAGE_REFRESH_INTERVAL_SECONDS,
        "urgent_refresh_interval_seconds": (
            PACKAGE_URGENT_REFRESH_INTERVAL_SECONDS
        ),
        "carriers": [
            {
                "key": key,
                "name": value["name"],
                "color": value["color"],
            }
            for key, value in CARRIERS.items()
        ],
        "statuses": [
            {"key": key, "label": label}
            for key, label in PACKAGE_STATUSES.items()
        ],
        "packages": [
            serialize_package(package)
            for package in get_packages()
        ],
    })


@app.route(
    "/api/packages",
    methods=["POST"],
)
def add_package():
    data = request.get_json(silent=True) or {}
    name = validate_package_text(data.get("name"), 80, required=True)
    tracking_number = normalize_tracking_number(
        data.get("tracking_number")
    )
    requested_carrier = data.get("carrier", "auto")
    expected_delivery = validate_package_date(
        data.get("expected_delivery")
    )
    note = validate_package_text(data.get("note"), 240)
    destination_post_code = validate_package_text(
        data.get("destination_post_code"),
        12,
    )

    if not ship24_is_configured():
        return jsonify({
            "success": False,
            "error": (
                "Automatisches Tracking ist noch nicht eingerichtet. "
                "SHIP24_API_KEY fehlt."
            ),
        }), 503

    if name is None:
        return jsonify({
            "success": False,
            "error": "Bitte eine Bezeichnung eingeben",
        }), 400

    if not 6 <= len(tracking_number) <= 40:
        return jsonify({
            "success": False,
            "error": "Bitte eine gültige Sendungsnummer eingeben",
        }), 400

    if expected_delivery is False:
        return jsonify({
            "success": False,
            "error": "Das Lieferdatum ist ungültig",
        }), 400

    if requested_carrier == "auto":
        carrier = detect_carrier(tracking_number)
    elif requested_carrier in CARRIERS:
        carrier = requested_carrier
    else:
        return jsonify({
            "success": False,
            "error": "Der Dienstleister ist ungültig",
        }), 400

    try:
        package_id = create_package(
            name,
            tracking_number,
            carrier,
            "announced",
            expected_delivery,
            note,
            destination_post_code,
        )
    except sqlite3.IntegrityError:
        return jsonify({
            "success": False,
            "error": "Diese Sendungsnummer ist bereits vorhanden",
        }), 409

    save_event(
        event_type="package",
        source_id=f"package:{package_id}",
        room=None,
        title=f"Paket hinzugefügt: {name}",
        detail=CARRIERS[carrier]["name"],
    )

    refresh_result = refresh_packages(package_id, live=True)

    return jsonify({
        "success": True,
        "package_id": package_id,
        "tracking": refresh_result,
    }), 201


@app.route(
    "/api/packages/refresh",
    methods=["POST"],
)
def refresh_package_entries():
    if not ship24_is_configured():
        return jsonify({
            "success": False,
            "error": "SHIP24_API_KEY fehlt",
        }), 503

    result = refresh_packages(force=True, live=True)

    return jsonify({
        "success": True,
        **result,
    })


@app.route(
    "/api/packages/<int:package_id>",
    methods=["DELETE"],
)
def remove_package(package_id):
    package = next(
        (
            item
            for item in get_packages()
            if item["id"] == package_id
        ),
        None,
    )

    if not delete_package(package_id):
        return jsonify({
            "success": False,
            "error": "Paket nicht gefunden",
        }), 404

    if package:
        unsubscribe_ship24_tracker(
            package.get("ship24_tracker_id")
        )

    return jsonify({"success": True})


# =============================================================
# API - EVENTS
# =============================================================

@app.route(
    "/api/camera/live"
)
def get_camera_live_stream():
    try:
        frames = open_camera_stream()
    except CameraStreamUnavailable as error:
        return jsonify({
            "success": False,
            "error": str(error),
        }), 503
    except CameraStreamBusy:
        return jsonify({
            "success": False,
            "error": "viewer_limit",
        }), 429

    response = Response(
        stream_with_context(frames),
        content_type=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        ),
    )
    response.headers[
        "Cache-Control"
    ] = "no-store, private"
    response.headers[
        "X-Accel-Buffering"
    ] = "no"

    return response


@app.route(
    "/api/camera/events"
)
def get_camera_events():
    stream_status = get_camera_stream_status()

    try:
        days = int(
            request.args.get(
                "days",
                CAMERA_EVENT_DAYS,
            )
        )
    except (TypeError, ValueError):
        days = CAMERA_EVENT_DAYS

    days = max(
        1,
        min(days, CAMERA_EVENT_DAYS),
    )

    start = (
        datetime.now()
        - timedelta(days=days - 1)
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    events = get_events_since(
        event_type="motion",
        since_timestamp=int(
            start.timestamp()
        ),
        source_id=(
            CAMERA_EVENT_SOURCE_ID
            or None
        ),
        limit=1000,
    )

    return jsonify({
        "success": True,
        "camera": {
            "name": CAMERA_NAME,
            "event_source_id": (
                CAMERA_EVENT_SOURCE_ID
                or None
            ),
            **stream_status,
        },
        "days": days,
        "events": events,
        "generated_at": int(
            time.time()
        ),
    })


@app.route(
    "/api/events"
)
def get_events():
    try:
        limit = int(
            request.args.get(
                "limit",
                30,
            )
        )

        before_timestamp = (
            request.args.get(
                "before_timestamp"
            )
        )
        before_id = request.args.get(
            "before_id"
        )

        if (
            before_timestamp is None
            or before_id is None
        ):
            before_timestamp = None
            before_id = None

        else:
            before_timestamp = int(
                before_timestamp
            )
            before_id = int(before_id)

    except (TypeError, ValueError):
        limit = 30
        before_timestamp = None
        before_id = None

    limit = max(1, min(limit, 99))

    events = get_recent_events(
        limit + 1,
        before_timestamp,
        before_id,
    )

    has_more = len(events) > limit
    events = events[:limit]

    next_cursor = None

    if events:
        oldest_event = events[-1]
        next_cursor = {
            "timestamp": oldest_event[
                "timestamp"
            ],
            "id": oldest_event["id"],
        }

    return jsonify({
        "success": True,
        "events": events,
        "has_more": has_more,
        "next_cursor": next_cursor,
    })


@app.route(
    "/api/event",
    methods=[
        "POST",
    ],
)
def create_custom_event():
    data = (
        request.get_json()
    )

    if not data:
        return jsonify({
            "success": False,
            "error":
                "No JSON data received",
        }), 400

    title = (
        data.get(
            "title"
        )
    )

    if not title:
        return jsonify({
            "success": False,
            "error":
                "Missing title",
        }), 400

    event_type = (
        data.get(
            "type",
            "custom",
        )
    )

    source_id = (
        data.get(
            "source"
        )
    )

    room = (
        data.get(
            "room"
        )
    )

    detail = (
        data.get(
            "detail"
        )
    )

    event_id = (
        save_event(
            event_type=event_type,
            source_id=source_id,
            room=room,
            title=title,
            detail=detail,
        )
    )

    print(
        "[EVENT] "
        f"{room or 'System'} / "
        f"{title}"
    )

    return jsonify({
        "success": True,
        "event_id": event_id,
    })


# =============================================================
# FULL SYNC
# =============================================================

@app.route(
    "/api/sync",
    methods=[
        "POST",
    ],
)
def sync_devices():
    data = (
        request.get_json()
    )

    if not data:
        return jsonify({
            "success": False,
            "error":
                "No JSON data received",
        }), 400

    updated = []
    unknown = []

    updated_sensor_fields = {}

    for key, value in (
        data.items()
    ):

        # =====================================================
        # SENSOR / KLIMA
        # =====================================================

        if key.startswith(
            "sensor_"
        ):
            sensor_update = (
                update_sensor(
                    key,
                    value,
                    log_update=(
                        key
                        not in {
                            "sensor_hallway_pm25",
                            "sensor_hallway_iai",
                        }
                    ),
                    log_unchanged=False,
                )
            )

            if sensor_update:
                room_id, sensor_type = (
                    sensor_update
                )

                updated.append(
                    key
                )

                updated_sensor_fields.setdefault(
                    room_id,
                    set(),
                ).add(
                    sensor_type
                )

            else:
                unknown.append(
                    key
                )

                print(
                    "[UNKNOWN SENSOR] "
                    f"{key} -> {value}"
                )

            continue


        # =====================================================
        # WASCHMASCHINE
        # =====================================================

        if (
            key
            == "device_washer_01_in_use"
        ):
            washer = devices[
                "device_washer_01"
            ]

            state_key = (
                "washer:in_use"
            )

            old_value = (
                washer[
                    "value"
                ]
            )

            new_value = (
                normalize_boolean(
                    value
                )
            )

            already_observed = (
                state_key
                in observed_states
            )

            if (
                (
                    already_observed
                    and old_value != new_value
                )
                or (
                    not already_observed
                    and new_value
                )
            ):
                create_device_event(
                    "device_washer_01",
                    old_value,
                    new_value,
                )

            washer[
                "value"
            ] = new_value

            save_device_state(
                "device_washer_01",
                new_value,
            )

            observed_states.add(
                state_key
            )

            print(
                "[device_washer_01] "
                f"{washer['room']} / {washer['name']} -> "
                f"{'Läuft' if new_value else 'Aus'}"
            )

            updated.append(
                key
            )

            continue


        if (
            key
            == "device_washer_01_remaining"
        ):
            washer = devices[
                "device_washer_01"
            ]

            washer[
                "remaining"
            ] = (
                normalize_duration(
                    value
                )
            )

            print(
                "[device_washer_01_remaining] "
                "Restzeit -> "
                f"{washer['remaining']} "
                "Sekunden"
            )

            updated.append(
                key
            )

            continue


        # =====================================================
        # AIR PURIFIER ACTIVE
        # =====================================================

        if (
            key
            == "device_air_filter_01_active"
        ):
            purifier = devices[
                "device_air_filter_01"
            ]

            state_key = (
                "purifier:active"
            )

            old_value = (
                purifier[
                    "active"
                ]
            )

            new_value = (
                normalize_boolean(
                    value
                )
            )

            already_observed = (
                state_key
                in observed_states
            )

            if (
                already_observed
                and old_value
                != new_value
            ):
                title = (
                    f"{purifier['name']} "
                    + (
                        "eingeschaltet"
                        if new_value
                        else
                        "ausgeschaltet"
                    )
                )

                save_event(
                    event_type=
                        "air_purifier",
                    source_id=
                        "device_air_filter_01",
                    room=purifier["room"],
                    title=title,
                )

            purifier[
                "active"
            ] = new_value

            observed_states.add(
                state_key
            )

            if (
                not already_observed
                or old_value != new_value
            ):
                print(
                    "[device_air_filter_01_active] "
                    "Air Purifier aktiv -> "
                    f"{new_value}"
                )

            updated.append(
                key
            )

            continue


        # =====================================================
        # AIR PURIFIER STATE
        # =====================================================

        if (
            key
            == "device_air_filter_01_state"
        ):
            purifier = devices[
                "device_air_filter_01"
            ]

            state_key = (
                "purifier:state"
            )

            old_state = (
                purifier[
                    "state"
                ]
            )

            new_state = (
                normalize_air_purifier_mode(
                    value
                )
            )

            already_observed = (
                state_key
                in observed_states
            )

            if (
                already_observed
                and old_state
                != new_state
                and new_state
                in {
                    "Auto",
                    "Sleep",
                    "Medium",
                    "Turbo",
                }
            ):
                save_event(
                    event_type=
                        "air_purifier",
                    source_id=
                        "device_air_filter_01",
                    room=purifier["room"],
                    title=
                        f"{purifier['name']} "
                        f"auf {new_state} gestellt",
                )

            purifier[
                "state"
            ] = new_state

            observed_states.add(
                state_key
            )

            if (
                not already_observed
                or old_state != new_state
            ):
                print(
                    "[device_air_filter_01_state] "
                    "Air Purifier State -> "
                    f"{purifier['state']}"
                )

            updated.append(
                key
            )

            continue


        # =====================================================
        # AIR PURIFIER SPEED
        # =====================================================

        if (
            key
            == "device_air_filter_01_speed"
        ):
            purifier = devices[
                "device_air_filter_01"
            ]

            state_key = (
                "purifier:speed"
            )

            old_speed = (
                purifier[
                    "speed"
                ]
            )

            new_speed = (
                normalize_number(
                    value
                )
            )

            already_observed = (
                state_key
                in observed_states
            )

            current_state = (
                purifier.get(
                    "state"
                )
            )

            if (
                already_observed
                and old_speed
                != new_speed
                and new_speed
                is not None
            ):
                mode = (
                    air_purifier_mode_from_speed(
                        new_speed
                    )
                )

                if (
                    current_state
                    == "Auto"
                    and old_speed
                    is not None
                    and new_speed
                    > old_speed
                ):
                    now = time.monotonic()
                    last_event_time = (
                        last_air_purifier_auto_event_times.get(
                            mode
                        )
                    )

                    if (
                        last_event_time
                        is None
                        or now
                        - last_event_time
                        >= AIR_PURIFIER_AUTO_EVENT_COOLDOWN_SECONDS
                    ):
                        save_event(
                            event_type=
                                "air_purifier",
                            source_id=
                                "device_air_filter_01",
                            room=purifier["room"],
                            title=
                                f"{purifier['name']} Stufe "
                                "automatisch auf "
                                f"{mode} erhöht",
                        )

                        last_air_purifier_auto_event_times[
                            mode
                        ] = now

                elif (
                    current_state
                    not in {
                        "Auto",
                        "Sleep",
                        "Medium",
                        "Turbo",
                    }
                ):
                    save_event(
                        event_type=
                            "air_purifier",
                        source_id=
                            "device_air_filter_01",
                        room=purifier["room"],
                        title=
                            f"{purifier['name']} "
                            f"auf {mode} gestellt",
                    )

            purifier[
                "speed"
            ] = new_speed

            observed_states.add(
                state_key
            )

            if (
                not already_observed
                or old_speed != new_speed
            ):
                print(
                    "[device_air_filter_01_speed] "
                    "Air Purifier Speed -> "
                    f"{new_speed}%"
                )

            updated.append(
                key
            )

            continue


        # =====================================================
        # NORMALE GERÄTE
        # =====================================================

        if key not in devices:
            unknown.append(
                key
            )

            print(
                f"[UNKNOWN] "
                f"{key} -> {value}"
            )

            continue

        normalized_value = (
            update_standard_device(
                key,
                value,
                log_first=False,
            )
        )

        updated.append(
            key
        )

        device = devices[
            key
        ]

        print(
            f"[{key}] "
            f"{device['room']} / "
            f"{device['name']} -> "
            f"{normalized_value}"
        )


    # =========================================================
    # SENSOR SNAPSHOTS
    # =========================================================

    for room_id in (
        updated_sensor_fields
    ):
        sensor = sensors[
            room_id
        ]

        now = time.monotonic()

        snapshot = {
            "temperature": None,
            "humidity": None,
            "pm25": None,
            "iai": None,
        }

        recorded_fields = []

        for sensor_type in (
            updated_sensor_fields[
                room_id
            ]
        ):
            snapshot_key = (
                room_id,
                sensor_type,
            )

            last_snapshot = (
                last_sensor_snapshot_times.get(
                    snapshot_key,
                    0,
                )
            )

            if (
                now - last_snapshot
                < SENSOR_HISTORY_INTERVAL_SECONDS
            ):
                continue

            snapshot[sensor_type] = (
                sensor.get(
                    sensor_type
                )
            )

            if snapshot[sensor_type] is not None:
                recorded_fields.append(
                    sensor_type
                )

        if not recorded_fields:
            continue

        save_sensor_snapshot(
            room_id,
            snapshot["temperature"],
            snapshot["humidity"],
            snapshot["pm25"],
            snapshot["iai"],
        )

        for sensor_type in recorded_fields:
            last_sensor_snapshot_times[
                (
                    room_id,
                    sensor_type,
                )
            ] = now

        print(
            "[HISTORY] "
            f"{sensor['name']} -> "
            "Snapshot gespeichert"
        )

    return jsonify({
        "success": True,
        "updated": updated,
        "unknown": unknown,
    })


# =============================================================
# START
# =============================================================

def main():
    if not acquire_single_instance():
        print(
            "[MONOLITH ERROR] "
            "app.py läuft bereits. "
            "Zweite Instanz wird beendet."
        )

        raise SystemExit(1)

    start_presence_monitor()
    start_lg_tv_monitor(
        update_lg_tv_status
    )
    start_homepod_monitor(
        update_homepod_status
    )
    start_apple_tv_monitor(
        update_apple_tv_status
    )
    start_pc_status_monitor(
        update_pc_status,
    )
    start_robovac_monitor(
        update_robovac_status
    )
    start_wewash_monitor(
        update_wewash_dryer_status
    )
    start_picnic_monitor(
        save_event
    )
    start_package_monitor()
    start_pet_monitor()
    start_network_monitor()
    start_switch_monitor(save_event)

    host = os.getenv(
        "MONOLITH_HOST",
        "0.0.0.0",
    )
    port = int(
        os.getenv(
            "MONOLITH_PORT",
            "5000",
        )
    )

    if os.getenv(
        "MONOLITH_DEBUG",
        "false",
    ).lower() in {"1", "true", "yes"}:
        app.run(
            host=host,
            port=port,
            debug=True,
            use_reloader=False,
        )
    else:
        from waitress import serve

        serve(
            app,
            host=host,
            port=port,
            threads=8,
        )


if __name__ == "__main__":
    main()
