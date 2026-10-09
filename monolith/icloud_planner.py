import copy
import hashlib
import os
import threading
import time
from datetime import date, datetime, timedelta


DEFAULT_CALDAV_URL = "https://caldav.icloud.com/"
DEFAULT_CACHE_SECONDS = 300
MAX_RANGE_DAYS = 70


_cache = {}
_cache_lock = threading.Lock()


def _split_names(value):
    return [
        item.strip()
        for item in (value or "").split(",")
        if item.strip()
    ]


def _settings():
    return {
        "username": os.getenv("ICLOUD_USERNAME", "").strip(),
        "password": os.getenv("ICLOUD_APP_PASSWORD", "").strip(),
        "url": (
            os.getenv("ICLOUD_CALDAV_URL", "").strip()
            or DEFAULT_CALDAV_URL
        ),
        "calendar_names": _split_names(
            os.getenv("ICLOUD_CALENDAR_NAMES")
        ),
    }


def _calendar_name(calendar):
    get_display_name = getattr(
        calendar,
        "get_display_name",
        None,
    )

    if callable(get_display_name):
        name = get_display_name()
    else:
        name = getattr(calendar, "name", None)

    if callable(name):
        name = name()

    return str(name or "Kalender").strip()


def _property_value(component, key, default=None):
    value = component.get(key, default)

    if value is default:
        return default

    if hasattr(value, "dt"):
        return value.dt

    if hasattr(value, "to_ical"):
        encoded = value.to_ical()
        if isinstance(encoded, bytes):
            return encoded.decode(
                "utf-8",
                errors="replace",
            )
        return encoded

    return value


def _text_value(component, key, default=""):
    value = _property_value(
        component,
        key,
        default,
    )

    if value is None:
        return default

    return str(value).strip()


def _iso_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if value in (None, ""):
        return None

    return str(value)


def _event_from_component(
    component,
    calendar_name,
):
    status = _text_value(
        component,
        "status",
    ).upper()

    if status == "CANCELLED":
        return None

    starts_at = _property_value(
        component,
        "dtstart",
    )

    if not isinstance(
        starts_at,
        (date, datetime),
    ):
        return None

    ends_at = _property_value(
        component,
        "dtend",
    )

    if ends_at is None:
        duration = _property_value(
            component,
            "duration",
        )

        if isinstance(duration, timedelta):
            ends_at = starts_at + duration
        else:
            ends_at = starts_at

    all_day = (
        isinstance(starts_at, date)
        and not isinstance(starts_at, datetime)
    )
    uid = _text_value(
        component,
        "uid",
    )
    identity = (
        f"{calendar_name}|{uid}|"
        f"{_iso_value(starts_at)}"
    )
    event_id = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:20]

    return {
        "id": event_id,
        "uid": uid,
        "title": (
            _text_value(component, "summary")
            or "Ohne Titel"
        ),
        "location": _text_value(
            component,
            "location",
        ),
        "calendar": calendar_name,
        "start": _iso_value(starts_at),
        "end": _iso_value(ends_at),
        "all_day": all_day,
    }


def _component(resource):
    return resource.get_icalendar_component()


def _matches_name(name, configured_names):
    if not configured_names:
        return True

    normalized = name.casefold()
    return any(
        normalized == candidate.casefold()
        for candidate in configured_names
    )


def _empty_result(settings):
    credentials_configured = bool(
        settings["username"]
        and settings["password"]
    )

    return {
        "success": True,
        "configured": credentials_configured,
        "calendar": {
            "status": (
                "loading"
                if credentials_configured
                else "setup"
            ),
            "events": [],
            "calendars": [],
            "message": (
                "iCloud-Zugang noch nicht eingerichtet"
                if not credentials_configured
                else ""
            ),
        },
        "synced_at": None,
    }


def _fetch_planner(start_date, end_date, settings):
    result = _empty_result(settings)

    if not result["configured"]:
        return result

    try:
        from caldav import DAVClient

        with DAVClient(
            url=settings["url"],
            username=settings["username"],
            password=settings["password"],
        ) as client:
            principal = client.principal()
            calendars = principal.get_calendars()

            calendar_names = []
            events = []
            calendar_failures = 0

            for calendar in calendars:
                name = _calendar_name(calendar)

                if not _matches_name(
                    name,
                    settings["calendar_names"],
                ):
                    continue

                try:
                    resources = calendar.search(
                        event=True,
                        start=start_date,
                        end=end_date,
                        expand=True,
                    )
                except Exception:
                    calendar_failures += 1
                    continue

                calendar_names.append(name)

                for resource in resources:
                    try:
                        event = _event_from_component(
                            _component(resource),
                            name,
                        )
                    except Exception:
                        continue

                    if event:
                        events.append(event)

            events.sort(
                key=lambda event: (
                    event["start"],
                    event["title"].casefold(),
                )
            )
            result["calendar"].update({
                "status": "ready",
                "events": events,
                "calendars": sorted(
                    set(calendar_names),
                    key=str.casefold,
                ),
                "message": (
                    "Einige Kalender konnten nicht geladen werden"
                    if calendar_failures
                    and calendar_names
                    else ""
                ),
            })

            result["synced_at"] = (
                datetime.now().astimezone().isoformat()
            )

    except ImportError:
        result["success"] = False
        result["calendar"].update({
            "status": "error",
            "message": "CalDAV-Abhängigkeit fehlt",
        })
    except Exception:
        result["success"] = False
        result["calendar"].update({
            "status": "error",
            "message": (
                "iCloud konnte nicht erreicht werden. "
                "Zugangsdaten und Verbindung prüfen"
            ),
        })

    return result


def get_icloud_planner(
    start_date,
    end_date,
    force_refresh=False,
):
    if not isinstance(start_date, date):
        raise ValueError("start_date must be a date")

    if not isinstance(end_date, date):
        raise ValueError("end_date must be a date")

    if end_date <= start_date:
        raise ValueError("end_date must be after start_date")

    if (end_date - start_date).days > MAX_RANGE_DAYS:
        raise ValueError("date range is too large")

    settings = _settings()
    cache_key = (
        start_date.isoformat(),
        end_date.isoformat(),
        settings["username"],
        bool(settings["password"]),
        tuple(settings["calendar_names"]),
    )

    try:
        cache_seconds = max(
            30,
            int(
                os.getenv(
                    "ICLOUD_CACHE_SECONDS",
                    DEFAULT_CACHE_SECONDS,
                )
            ),
        )
    except ValueError:
        cache_seconds = DEFAULT_CACHE_SECONDS

    with _cache_lock:
        cached = _cache.get(cache_key)

        if (
            not force_refresh
            and cached
            and time.monotonic()
            - cached["created_at"]
            < cache_seconds
        ):
            return copy.deepcopy(cached["value"])

    result = _fetch_planner(
        start_date,
        end_date,
        settings,
    )

    with _cache_lock:
        _cache[cache_key] = {
            "created_at": time.monotonic(),
            "value": copy.deepcopy(result),
        }

    return result
