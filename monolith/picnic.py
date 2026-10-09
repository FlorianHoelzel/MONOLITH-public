import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from python_picnic_api2 import (
    Picnic2FAError,
    Picnic2FARequired,
    PicnicAPI,
    PicnicAuthError,
)
from requests import RequestException

from monolith.data_paths import data_path

load_dotenv()


SESSION_PATH = data_path("picnic_session.json")

STATE_PATH = data_path("picnic_state.json")

PICNIC_IMAGE_BASE_URL = (
    "https://storefront-prod.de."
    "picnicinternational.com/static/images"
)

_lock = threading.RLock()
_client = None
_two_factor_required = False
_monitor_started = False
_status_cache = None
_status_cache_updated_at = 0.0

PICNIC_STATUS_CACHE_SECONDS = 300


def _credentials():
    return (
        os.getenv(
            "PICNIC_USERNAME",
            "",
        ).strip(),
        os.getenv(
            "PICNIC_PASSWORD",
            "",
        ),
        os.getenv(
            "PICNIC_COUNTRY_CODE",
            "DE",
        ).strip().upper() or "DE",
    )


def _load_auth_token():
    try:
        payload = json.loads(
            SESSION_PATH.read_text(
                encoding="utf-8"
            )
        )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
    ):
        return None

    token = payload.get("auth_token")

    if isinstance(token, str):
        return token.strip() or None

    return None


def _save_auth_token(client):
    token = client.session.auth_token

    if not token:
        return

    SESSION_PATH.write_text(
        json.dumps({
            "auth_token": token,
        }),
        encoding="utf-8",
    )


def _clear_auth_token():
    try:
        SESSION_PATH.unlink()
    except FileNotFoundError:
        pass


def _load_monitor_state():
    try:
        payload = json.loads(
            STATE_PATH.read_text(
                encoding="utf-8"
            )
        )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
    ):
        return {
            "orders": {},
        }

    if not isinstance(
        payload.get("orders"),
        dict,
    ):
        payload["orders"] = {}

    return payload


def _save_monitor_state(state):
    temporary_path = (
        STATE_PATH.with_suffix(".tmp")
    )
    temporary_path.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary_path.replace(
        STATE_PATH
    )


def _configured():
    username, password, _ = _credentials()

    return bool(
        _client
        or _load_auth_token()
        or (
            username
            and password
        )
    )


def _connect(force_password_login=False):
    global _client
    global _two_factor_required

    username, password, country_code = (
        _credentials()
    )

    auth_token = (
        None
        if force_password_login
        else _load_auth_token()
    )

    if (
        not auth_token
        and (
            not username
            or not password
        )
    ):
        return None

    client = PicnicAPI(
        country_code=country_code,
        auth_token=auth_token,
    )

    if not client.logged_in():
        try:
            client.login(
                username=username,
                password=password,
            )
        except Picnic2FARequired:
            _client = client
            _two_factor_required = True
            return client

    _client = client
    _two_factor_required = False
    _save_auth_token(client)

    return client


def login_picnic(
    username,
    password,
    country_code="DE",
):
    global _client
    global _two_factor_required

    normalized_username = str(
        username or ""
    ).strip()
    normalized_password = str(
        password or ""
    )
    normalized_country = str(
        country_code or "DE"
    ).strip().upper()

    if (
        not normalized_username
        or not normalized_password
    ):
        return _error_status(
            "Bitte gib E-Mail-Adresse und Passwort ein."
        )

    if normalized_country not in {
        "DE",
        "NL",
        "FR",
    }:
        normalized_country = "DE"

    with _lock:
        client = PicnicAPI(
            country_code=normalized_country,
        )

        try:
            client.login(
                username=normalized_username,
                password=normalized_password,
            )
        except Picnic2FARequired:
            _client = client
            _two_factor_required = True

            return {
                "success": True,
                "connected": False,
                "two_factor_required": True,
                "message": "Picnic benötigt eine SMS-Bestätigung.",
            }
        except (
            PicnicAuthError,
            RequestException,
        ) as error:
            return _error_status(
                "Picnic-Anmeldung fehlgeschlagen. Prüfe deine Zugangsdaten.",
                error,
            )

        _client = client
        _two_factor_required = False
        _save_auth_token(client)

        return {
            "success": True,
            "connected": True,
            "two_factor_required": False,
            "message": "Picnic wurde verbunden.",
        }


def _get_client():
    global _client

    if _client is None:
        return _connect()

    return _client


def _quantity_for_line(line):
    if not line.items:
        return 0

    for decorator in line.items[0].decorators:
        if (
            decorator.type == "QUANTITY"
            and decorator.quantity
        ):
            return decorator.quantity

    return len(line.items)


def _serialize_cart(cart):
    items = _serialize_order_lines(
        cart.items
    )

    return {
        "kind": "cart",
        "title": "Warenkorb",
        "total_count": cart.total_count or 0,
        "total_price": (
            cart.checkout_total_price
            if cart.checkout_total_price is not None
            else cart.total_price or 0
        ),
        "items": items,
    }


def _serialize_order_lines(lines):
    items = []

    for line in lines:
        if not line.items:
            continue

        article = line.items[0]
        quantity = _quantity_for_line(line)
        image_id = (
            article.image_ids[0]
            if article.image_ids
            else None
        )

        items.append({
            "id": article.id,
            "name": article.name or "Unbekannter Artikel",
            "quantity": quantity,
            "unit_quantity": article.unit_quantity,
            "image_url": (
                f"{PICNIC_IMAGE_BASE_URL}/"
                f"{image_id}/small.png"
                if image_id
                else None
            ),
            "unit_price": article.price,
            "line_price": (
                line.display_price
                if line.display_price is not None
                else line.price
            ),
        })

    return items


def _delivery_status(delivery):
    order_statuses = [
        order.status
        for order in delivery.orders
        if order.status
    ]

    specific_status = next(
        (
            status
            for status in order_statuses
            if status.upper() != "CURRENT"
        ),
        None,
    )

    return (
        specific_status
        or delivery.status
        or (
            order_statuses[0]
            if order_statuses
            else None
        )
    )


def _serialize_delivery(delivery):
    slot = delivery.slot
    eta = delivery.eta2
    total_price = sum(
        order.checkout_total_price
        if order.checkout_total_price is not None
        else order.total_price or 0
        for order in delivery.orders
    )

    return {
        "id": delivery.delivery_id,
        "status": _delivery_status(delivery),
        "window_start": (
            slot.window_start
            if slot
            else None
        ),
        "window_end": (
            slot.window_end
            if slot
            else None
        ),
        "eta_start": (
            eta.start
            if eta
            else None
        ),
        "eta_end": (
            eta.end
            if eta
            else None
        ),
        "total_price": total_price,
    }


def _serialize_active_order(delivery):
    summary = _serialize_delivery(
        delivery
    )
    lines = [
        line
        for order in delivery.orders
        for line in order.items
    ]
    items = _serialize_order_lines(lines)

    return {
        **summary,
        "kind": "order",
        "title": "Aktuelle Bestellung",
        "total_count": sum(
            item["quantity"]
            for item in items
        ),
        "items": items,
    }


def _delivery_sort_key(delivery):
    return (
        delivery.slot.window_start
        if delivery.slot
        and delivery.slot.window_start
        else delivery.creation_time or ""
    )


def get_picnic_status(force_refresh=False):
    global _client
    global _status_cache
    global _status_cache_updated_at

    with _lock:
        if (
            not force_refresh
            and _status_cache is not None
            and time.monotonic()
            - _status_cache_updated_at
            < PICNIC_STATUS_CACHE_SECONDS
        ):
            return _status_cache

        if not _configured():
            return {
                "success": True,
                "configured": False,
                "connected": False,
                "two_factor_required": False,
                "active_purchase": None,
                "current_order": None,
                "recent_deliveries": [],
            }

        try:
            client = _get_client()

            if _two_factor_required:
                return {
                    "success": True,
                    "configured": True,
                    "connected": False,
                    "two_factor_required": True,
                    "active_purchase": None,
                    "current_order": None,
                    "recent_deliveries": [],
                }

            cart = client.get_cart()
            current_deliveries = (
                client.get_current_deliveries()
            )
            all_deliveries = sorted(
                client.get_deliveries(),
                key=_delivery_sort_key,
                reverse=True,
            )

            current_order = None
            active_purchase = (
                _serialize_cart(cart)
            )

            if current_deliveries:
                current_summary = sorted(
                    current_deliveries,
                    key=_delivery_sort_key,
                )[0]
                current_detail = (
                    client.get_delivery(
                        current_summary.delivery_id
                    )
                )
                current_order = (
                    _serialize_delivery(
                        current_detail
                    )
                )
                active_purchase = (
                    _serialize_active_order(
                        current_detail
                    )
                )
                is_underway = (
                    _delivery_is_underway(
                        client,
                        current_detail,
                    )
                )
                current_order["is_underway"] = (
                    is_underway
                )
                active_purchase["is_underway"] = (
                    is_underway
                )

            current_ids = {
                delivery.delivery_id
                for delivery in current_deliveries
            }
            recent_deliveries = [
                _serialize_delivery(delivery)
                for delivery in all_deliveries
                if delivery.delivery_id
                not in current_ids
                and str(
                    _delivery_status(delivery)
                    or ""
                ).upper() not in {
                    "CANCELLED",
                    "CANCELED",
                }
            ]

            _save_auth_token(client)

            status = {
                "success": True,
                "configured": True,
                "connected": True,
                "two_factor_required": False,
                "active_purchase": active_purchase,
                "current_order": current_order,
                "recent_deliveries": recent_deliveries,
            }
            _status_cache = status
            _status_cache_updated_at = time.monotonic()

            return status

        except PicnicAuthError:
            _client = None
            _clear_auth_token()

            try:
                _connect(
                    force_password_login=True
                )
            except PicnicAuthError as error:
                return _error_status(
                    "Picnic-Anmeldung fehlgeschlagen.",
                    error,
                )

            if _two_factor_required:
                return {
                    "success": True,
                    "configured": True,
                    "connected": False,
                    "two_factor_required": True,
                    "active_purchase": None,
                    "current_order": None,
                    "recent_deliveries": [],
                }

            return get_picnic_status(
                force_refresh=True
            )

        except (
            Picnic2FAError,
            RequestException,
            OSError,
            ValueError,
        ) as error:
            return _error_status(
                "Picnic ist gerade nicht erreichbar.",
                error,
            )


def _error_status(message, error=None):
    if error:
        print(
            "[PICNIC ERROR]",
            repr(error),
        )

    return {
        "success": False,
        "configured": _configured(),
        "connected": False,
        "two_factor_required": (
            _two_factor_required
        ),
        "error": message,
        "active_purchase": None,
        "current_order": None,
        "recent_deliveries": [],
    }


def get_picnic_delivery_details(
    delivery_id,
):
    normalized_id = str(
        delivery_id or ""
    ).strip()

    if (
        not normalized_id
        or not normalized_id.isalnum()
        or len(normalized_id) > 64
    ):
        return {
            "success": False,
            "error": "Ungültige Lieferungs-ID.",
            "delivery": None,
        }

    with _lock:
        if not _configured():
            return {
                "success": False,
                "error": "Picnic ist noch nicht verbunden.",
                "delivery": None,
            }

        try:
            client = _get_client()
            delivery = client.get_delivery(
                normalized_id
            )
            serialized = (
                _serialize_active_order(
                    delivery
                )
            )
            serialized["title"] = (
                "Vergangene Bestellung"
            )

            return {
                "success": True,
                "delivery": serialized,
            }

        except (
            PicnicAuthError,
            RequestException,
            OSError,
            ValueError,
        ) as error:
            print(
                "[PICNIC DELIVERY ERROR]",
                repr(error),
            )

            return {
                "success": False,
                "error": "Die Bestellung konnte nicht geladen werden.",
                "delivery": None,
            }


def _format_euro(cents):
    amount = (
        int(cents or 0)
        / 100
    )

    return (
        f"{amount:,.2f}"
        .replace(",", "_")
        .replace(".", ",")
        .replace("_", ".")
        + " €"
    )


def _parse_picnic_date(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def _should_check_delivery_position(
    delivery,
):
    eta = delivery.eta2
    slot = delivery.slot
    start = _parse_picnic_date(
        (
            eta.start
            if eta and eta.start
            else slot.window_start
            if slot
            else None
        )
    )
    end = _parse_picnic_date(
        (
            eta.end
            if eta and eta.end
            else slot.window_end
            if slot
            else None
        )
    )

    if not start:
        return False

    now = datetime.now(
        start.tzinfo
    )
    check_from = start - timedelta(
        hours=3
    )
    check_until = (
        end or start
    ) + timedelta(hours=2)

    return check_from <= now <= check_until


def _delivery_is_underway(
    client,
    delivery,
):
    if not _should_check_delivery_position(
        delivery
    ):
        return False

    try:
        position = client.get_delivery_position(
            delivery.delivery_id
        )
    except PicnicAuthError:
        raise
    except (
        RequestException,
        OSError,
        TypeError,
        ValueError,
    ):
        return False

    if (
        isinstance(position, dict)
        and position.get("error")
    ):
        return False

    return bool(position)


def _format_delivery_schedule(
    start_value,
    end_value,
    include_day=True,
):
    start = _parse_picnic_date(
        start_value
    )
    end = _parse_picnic_date(
        end_value
    )

    if not start:
        return "Termin noch offen"

    day_names = [
        "Montag",
        "Dienstag",
        "Mittwoch",
        "Donnerstag",
        "Freitag",
        "Samstag",
        "Sonntag",
    ]
    time_range = start.strftime(
        "%H:%M"
    )

    if end:
        time_range += (
            "–"
            + end.strftime("%H:%M")
        )

    time_range += " Uhr"

    if not include_day:
        return time_range

    return (
        f"{day_names[start.weekday()]}, "
        f"{time_range}"
    )


def _emit_picnic_event(
    callback,
    title,
    detail=None,
):
    try:
        callback(
            event_type="picnic",
            source_id="picnic_order",
            room="Picnic",
            title=title,
            detail=detail,
        )
        return True
    except Exception as error:
        print(
            "[PICNIC MONITOR ERROR]",
            repr(error),
        )
        return False


def _check_picnic_events(callback):
    data = get_picnic_status()

    if (
        not data.get("success")
        or not data.get("connected")
    ):
        return

    state = _load_monitor_state()
    orders = state["orders"]
    changed = False
    current = data.get(
        "current_order"
    )
    active_purchase = data.get(
        "active_purchase"
    ) or {}

    if current and current.get("id"):
        order_id = current["id"]
        order_state = orders.setdefault(
            order_id,
            {
                "ordered": False,
                "window_planned": False,
                "delivery_underway": False,
                "delivered": False,
            },
        )

        if not order_state.get("ordered"):
            total = _format_euro(
                active_purchase.get(
                    "total_price",
                    current.get("total_price"),
                )
            )
            schedule = (
                _format_delivery_schedule(
                    current.get("window_start"),
                    current.get("window_end"),
                )
            )

            if _emit_picnic_event(
                callback,
                f"Bestellung über {total} erfolgreich.",
                f"Geplant für {schedule}.",
            ):
                order_state["ordered"] = True
                changed = True

        eta_start = current.get(
            "eta_start"
        )
        eta_end = current.get(
            "eta_end"
        )
        window_was_reported = bool(
            order_state.get(
                "window_planned"
            )
            or order_state.get("underway")
            or order_state.get(
                "underway_window"
            )
        )

        if (
            eta_start
            and not window_was_reported
        ):
            window = _format_delivery_schedule(
                eta_start,
                eta_end,
                include_day=False,
            )

            if _emit_picnic_event(
                callback,
                "Zustellfenster geplant.",
                f"Zeitfenster: {window}.",
            ):
                order_state[
                    "window_planned"
                ] = True
                changed = True

        if (
            current.get("is_underway")
            and not order_state.get(
                "delivery_underway"
            )
        ):
            window = _format_delivery_schedule(
                eta_start,
                eta_end,
                include_day=False,
            )

            if _emit_picnic_event(
                callback,
                "Bestellung unterwegs.",
                f"Zeitfenster: {window}.",
            ):
                order_state[
                    "delivery_underway"
                ] = True
                changed = True

    delivered_orders = {
        delivery.get("id")
        for delivery in data.get(
            "recent_deliveries",
            [],
        )
        if str(
            delivery.get("status")
            or ""
        ).upper() in {
            "COMPLETED",
            "DELIVERED",
        }
    }

    for order_id, order_state in (
        orders.items()
    ):
        if (
            order_id in delivered_orders
            and order_state.get("ordered")
            and not order_state.get(
                "delivered"
            )
        ):
            if _emit_picnic_event(
                callback,
                "Bestellung zugestellt.",
            ):
                order_state["delivered"] = True
                changed = True

    if changed:
        _save_monitor_state(state)


def start_picnic_monitor(
    callback,
    interval=300,
):
    global _monitor_started

    if _monitor_started:
        return

    _monitor_started = True

    def monitor():
        while True:
            try:
                _check_picnic_events(
                    callback
                )
            except Exception as error:
                print(
                    "[PICNIC MONITOR ERROR]",
                    repr(error),
                )

            threading.Event().wait(
                interval
            )

    threading.Thread(
        target=monitor,
        name="picnic-monitor",
        daemon=True,
    ).start()


def request_picnic_2fa():
    with _lock:
        if not _configured():
            return _error_status(
                "Picnic ist noch nicht konfiguriert."
            )

        try:
            client = _get_client()

            if not _two_factor_required:
                return {
                    "success": True,
                    "required": False,
                    "message": "Picnic ist bereits verbunden.",
                }

            client.generate_2fa_code(
                channel="SMS"
            )

            return {
                "success": True,
                "required": True,
                "message": "SMS-Code wurde angefordert.",
            }

        except (
            PicnicAuthError,
            Picnic2FAError,
            RequestException,
        ) as error:
            return _error_status(
                "Der SMS-Code konnte nicht angefordert werden.",
                error,
            )


def verify_picnic_2fa(code):
    global _two_factor_required

    normalized_code = str(
        code or ""
    ).strip()

    if not normalized_code:
        return _error_status(
            "Bitte gib den SMS-Code ein."
        )

    with _lock:
        try:
            client = _get_client()

            if client is None:
                return _error_status(
                    "Picnic ist noch nicht konfiguriert."
                )

            client.verify_2fa_code(
                normalized_code
            )
            _two_factor_required = False
            _save_auth_token(client)

            return {
                "success": True,
                "message": "Picnic wurde verbunden.",
            }

        except (
            PicnicAuthError,
            Picnic2FAError,
            RequestException,
        ) as error:
            return _error_status(
                "Der SMS-Code ist ungültig oder abgelaufen.",
                error,
            )
