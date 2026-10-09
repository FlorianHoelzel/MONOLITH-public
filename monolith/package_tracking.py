import os
import re
from datetime import datetime
from urllib.parse import quote

import requests


SHIP24_API_BASE_URL = "https://api.ship24.com/public/v1"
SHIP24_TIMEOUT_SECONDS = 30
SHIP24_TRACK_TIMEOUT_SECONDS = 75


class PackageTrackingError(RuntimeError):
    pass


CARRIERS = {
    "dhl": {
        "name": "DHL",
        "color": "#ffcc00",
        "tracking_url": (
            "https://www.dhl.de/de/privatkunden/"
            "dhl-sendungsverfolgung.html?piececode={number}"
        ),
    },
    "deutsche_post": {
        "name": "Deutsche Post",
        "color": "#ffcc00",
        "tracking_url": (
            "https://www.deutschepost.de/sendung/simpleQuery.html"
            "?form.sendungsnummer={number}"
        ),
    },
    "hermes": {
        "name": "Hermes",
        "color": "#0091cd",
        "tracking_url": (
            "https://www.myhermes.de/empfangen/sendungsverfolgung/"
            "sendungsinformation/#{number}"
        ),
    },
    "dpd": {
        "name": "DPD",
        "color": "#dc0032",
        "tracking_url": (
            "https://tracking.dpd.de/status/de_DE/parcel/{number}"
        ),
    },
    "gls": {
        "name": "GLS",
        "color": "#ffd100",
        "tracking_url": (
            "https://gls-group.com/GROUP/en/parcel-tracking/"
            "?match={number}"
        ),
    },
    "ups": {
        "name": "UPS",
        "color": "#ffb500",
        "tracking_url": (
            "https://www.ups.com/track?loc=de_DE&tracknum={number}"
        ),
    },
    "fedex": {
        "name": "FedEx",
        "color": "#ff6600",
        "tracking_url": (
            "https://www.fedex.com/fedextrack/?trknbr={number}"
        ),
    },
    "amazon": {
        "name": "Amazon Logistics",
        "color": "#ff9900",
        "tracking_url": (
            "https://www.amazon.de/progress-tracker/package/"
            "ref=ppx_yo_dt_b_track_package"
        ),
    },
    "tnt": {
        "name": "TNT",
        "color": "#ff6600",
        "tracking_url": (
            "https://www.tnt.com/express/de_de/site/shipping-tools/"
            "tracking.html?searchType=con&cons={number}"
        ),
    },
    "other": {
        "name": "Anderer Dienstleister",
        "color": "#a0a0a7",
        "tracking_url": None,
    },
}


PACKAGE_STATUSES = {
    "announced": "Angekündigt",
    "in_transit": "Unterwegs",
    "out_for_delivery": "In Zustellung",
    "failed_attempt": "Zustellversuch",
    "ready_for_pickup": "Abholbereit",
    "delivered": "Zugestellt",
    "exception": "Problem",
}


SHIP24_STATUS_MAP = {
    "pending": "announced",
    "info_received": "announced",
    "in_transit": "in_transit",
    "out_for_delivery": "out_for_delivery",
    "failed_attempt": "failed_attempt",
    "available_for_pickup": "ready_for_pickup",
    "delivered": "delivered",
    "exception": "exception",
}


# Ship24's courier codes are not always identical to the labels used by the
# dashboard.  Supplying the code is especially important for purely numeric
# tracking numbers, which can otherwise match several carriers.
SHIP24_COURIER_CODES = {
    "dhl": "dhl",
}


def normalize_tracking_number(value):
    return re.sub(
        r"[\s-]+",
        "",
        str(value or "").strip(),
    ).upper()


def detect_carrier(tracking_number):
    number = normalize_tracking_number(tracking_number)

    if re.fullmatch(r"1Z[0-9A-Z]{16}", number):
        return "ups"

    if re.fullmatch(r"TBA[0-9A-Z]{9,15}", number):
        return "amazon"

    if re.fullmatch(r"[A-Z]{2}\d{9}DE", number):
        return "deutsche_post"

    if re.fullmatch(r"JJD\d{15,21}", number):
        return "dhl"

    if re.fullmatch(r"(?:00340434|00340433|00340000)\d{12,14}", number):
        return "dhl"

    if re.fullmatch(r"\d{14}", number):
        return "hermes"

    if re.fullmatch(r"\d{11}", number):
        return "dpd"

    if re.fullmatch(r"\d{8}", number):
        return "gls"

    if re.fullmatch(r"\d{12}|\d{15}|\d{20}|\d{22}", number):
        return "fedex"

    if re.fullmatch(r"\d{9}", number):
        return "tnt"

    if re.fullmatch(r"\d{10}|\d{16}|\d{20}", number):
        return "dhl"

    return "other"


def carrier_details(carrier, tracking_number):
    carrier_key = carrier if carrier in CARRIERS else "other"
    details = dict(CARRIERS[carrier_key])
    template = details.pop("tracking_url")
    details["key"] = carrier_key
    details["tracking_url"] = (
        template.format(
            number=quote(
                normalize_tracking_number(tracking_number),
                safe="",
            )
        )
        if template
        else None
    )
    return details


def ship24_is_configured():
    return bool(os.getenv("SHIP24_API_KEY", "").strip())


def _ship24_headers():
    api_key = os.getenv("SHIP24_API_KEY", "").strip()

    if not api_key:
        raise PackageTrackingError(
            "Automatisches Tracking ist noch nicht eingerichtet"
        )

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }


def _ship24_request(method, path, json=None, timeout=SHIP24_TIMEOUT_SECONDS):
    try:
        response = requests.request(
            method,
            f"{SHIP24_API_BASE_URL}{path}",
            headers=_ship24_headers(),
            json=json,
            timeout=timeout,
        )
    except requests.RequestException as error:
        raise PackageTrackingError(
            "Tracking-Dienst ist momentan nicht erreichbar"
        ) from error

    if response.ok:
        try:
            return response.json()
        except ValueError as error:
            raise PackageTrackingError(
                "Tracking-Dienst hat ungültige Daten geliefert"
            ) from error

    try:
        payload = response.json()
        errors = payload.get("errors") or []
        message = errors[0].get("message") if errors else None
    except (ValueError, AttributeError, IndexError):
        message = None

    if response.status_code in (401, 403):
        message = "Ship24 API-Schlüssel ist ungültig oder das Kontingent ist aufgebraucht"

    raise PackageTrackingError(
        message or f"Tracking-Dienst meldet Fehler {response.status_code}"
    )


def _ship24_tracker_payload(
    tracking_number,
    client_tracker_id,
    title,
    destination_post_code=None,
    carrier=None,
):
    payload = {
        "trackingNumber": normalize_tracking_number(tracking_number),
        "clientTrackerId": client_tracker_id,
        "shipmentReference": client_tracker_id,
        "destinationCountryCode": "DE",
        "title": title,
    }

    if destination_post_code:
        payload["destinationPostCode"] = destination_post_code

    courier_code = SHIP24_COURIER_CODES.get(carrier)

    if courier_code:
        payload["courierCode"] = [courier_code]

    return payload


def _ship24_lookup_payload(
    tracking_number,
    destination_post_code=None,
    carrier=None,
):
    payload = {
        "trackingNumber": normalize_tracking_number(tracking_number),
        "destinationCountryCode": "DE",
    }

    if destination_post_code:
        payload["destinationPostCode"] = destination_post_code

    courier_code = SHIP24_COURIER_CODES.get(carrier)

    if courier_code:
        payload["courierCode"] = [courier_code]

    return payload


def register_ship24_tracker(
    tracking_number,
    client_tracker_id,
    title,
    destination_post_code=None,
    carrier=None,
):
    result = _ship24_request(
        "POST",
        "/trackers",
        json=_ship24_tracker_payload(
            tracking_number,
            client_tracker_id,
            title,
            destination_post_code,
            carrier,
        ),
    )
    tracker = (result.get("data") or {}).get("tracker") or {}
    tracker_id = tracker.get("trackerId")

    if not tracker_id:
        raise PackageTrackingError(
            "Tracking-Dienst hat keine Tracker-ID geliefert"
        )

    return tracker_id


def track_ship24_shipment(
    tracking_number,
    client_tracker_id,
    title,
    destination_post_code=None,
    carrier=None,
):
    """Synchronously fetch current results using the idempotent tracker API."""
    result = _ship24_request(
        "POST",
        "/trackers/track",
        json=_ship24_tracker_payload(
            tracking_number,
            client_tracker_id,
            title,
            destination_post_code,
            carrier,
        ),
        timeout=SHIP24_TRACK_TIMEOUT_SECONDS,
    )
    data = result.get("data") or {}
    trackings = data.get("trackings") or []
    tracker = data.get("tracker") or {}

    if not tracker and trackings:
        tracker = trackings[0].get("tracker") or {}

    tracking = {
        "tracker_id": tracker.get("trackerId"),
        **_normalize_ship24_trackings(trackings),
        "used_per_call": False,
    }

    if tracking["events"]:
        return tracking

    # Persistent trackers occasionally remain empty even though the courier
    # already exposes events. Use the separately subscribed per-call product
    # only for explicit live operations, never for background polling.
    fallback_result = _ship24_request(
        "POST",
        "/tracking/search",
        json=_ship24_lookup_payload(
            tracking_number,
            destination_post_code,
            carrier,
        ),
        timeout=SHIP24_TRACK_TIMEOUT_SECONDS,
    )
    fallback_tracking = _normalize_ship24_trackings(
        (fallback_result.get("data") or {}).get("trackings") or []
    )

    return {
        "tracker_id": tracking["tracker_id"],
        **fallback_tracking,
        "used_per_call": True,
    }


def configure_ship24_tracker_courier(tracker_id, carrier):
    courier_code = SHIP24_COURIER_CODES.get(carrier)

    if not courier_code:
        return False

    _ship24_request(
        "PATCH",
        f"/trackers/{quote(str(tracker_id), safe='')}",
        json={"courierCode": [courier_code]},
    )
    return True


def _normalize_ship24_trackings(trackings):
    if not trackings:
        return {
            "status": "announced",
            "expected_delivery": None,
            "events": [],
        }

    events_by_id = {}
    fallback_status = "announced"
    expected_delivery = None

    for tracking in trackings:
        shipment = tracking.get("shipment") or {}
        delivery = shipment.get("delivery") or {}
        courier_window = delivery.get("courierEstimatedDeliveryDate") or {}
        delivery_value = (
            courier_window.get("from")
            or delivery.get("estimatedDeliveryDate")
        )

        if expected_delivery is None and delivery_value:
            expected_delivery = str(delivery_value)[:10]

        shipment_status = SHIP24_STATUS_MAP.get(
            shipment.get("statusMilestone"),
        )

        if shipment_status and shipment_status != "announced":
            fallback_status = shipment_status

        for item in tracking.get("events") or []:
            event_id = item.get("eventId")

            if not event_id:
                continue

            occurred_at = parse_ship24_datetime(
                item.get("occurrenceDatetime")
            )
            events_by_id[event_id] = {
                "event_id": event_id,
                "status": SHIP24_STATUS_MAP.get(
                    item.get("statusMilestone"),
                    shipment_status or fallback_status,
                ),
                "detail": item.get("status") or "Status aktualisiert",
                "location": item.get("location"),
                "occurred_at": occurred_at,
                "_order": item.get("order") or 0,
            }

    events = sorted(
        events_by_id.values(),
        key=lambda item: (item["occurred_at"] or 0, item["_order"]),
        reverse=True,
    )
    status = events[0]["status"] if events else fallback_status

    for event in events:
        event.pop("_order", None)

    return {
        "status": status,
        "expected_delivery": expected_delivery,
        "events": events,
    }


def fetch_ship24_tracking(tracker_id):
    result = _ship24_request(
        "GET",
        f"/trackers/{quote(str(tracker_id), safe='')}/results",
    )
    trackings = (result.get("data") or {}).get("trackings") or []

    return _normalize_ship24_trackings(trackings)


def unsubscribe_ship24_tracker(tracker_id):
    if not tracker_id or not ship24_is_configured():
        return

    try:
        _ship24_request(
            "PATCH",
            f"/trackers/{quote(str(tracker_id), safe='')}",
            json={"isSubscribed": False},
        )
    except PackageTrackingError:
        pass


def parse_ship24_datetime(value):
    if not value:
        return None

    normalized = str(value).strip()

    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        return int(datetime.fromisoformat(normalized).timestamp())
    except ValueError:
        return None
