"""Weather and geocoding clients for the weather workspace."""

from datetime import date
import re

import requests


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
POSTAL_GEOCODING_URL = "https://nominatim.openstreetmap.org/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 12
GERMAN_POSTAL_CODE_PATTERN = re.compile(r"^(\d{5})(?:\s+.*)?$")
NOMINATIM_LOCATION_ID_OFFSET = 1_000_000_000_000

CURRENT_FIELDS = (
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation_probability",
    "precipitation",
    "rain",
    "showers",
    "snowfall",
    "weather_code",
    "cloud_cover",
    "pressure_msl",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "visibility",
    "uv_index",
    "is_day",
)

HOURLY_FIELDS = CURRENT_FIELDS

DAILY_FIELDS = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "sunrise",
    "sunset",
    "daylight_duration",
    "sunshine_duration",
    "uv_index_max",
    "precipitation_sum",
    "rain_sum",
    "showers_sum",
    "snowfall_sum",
    "precipitation_hours",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
)

HOURLY_NAMES = {
    "temperature_2m": "temperature",
    "apparent_temperature": "apparent_temperature",
    "relative_humidity_2m": "relative_humidity",
    "precipitation_probability": "precipitation_probability",
    "precipitation": "precipitation",
    "rain": "rain",
    "showers": "showers",
    "snowfall": "snowfall",
    "weather_code": "weather_code",
    "cloud_cover": "cloud_cover",
    "pressure_msl": "pressure_msl",
    "surface_pressure": "surface_pressure",
    "wind_speed_10m": "wind_speed",
    "wind_direction_10m": "wind_direction",
    "wind_gusts_10m": "wind_gusts",
    "visibility": "visibility",
    "uv_index": "uv_index",
    "is_day": "is_day",
}

DAILY_NAMES = {
    "weather_code": "weather_code",
    "temperature_2m_max": "temperature_max",
    "temperature_2m_min": "temperature_min",
    "apparent_temperature_max": "apparent_temperature_max",
    "apparent_temperature_min": "apparent_temperature_min",
    "sunrise": "sunrise",
    "sunset": "sunset",
    "daylight_duration": "daylight_duration",
    "sunshine_duration": "sunshine_duration",
    "uv_index_max": "uv_index_max",
    "precipitation_sum": "precipitation_sum",
    "rain_sum": "rain_sum",
    "showers_sum": "showers_sum",
    "snowfall_sum": "snowfall_sum",
    "precipitation_hours": "precipitation_hours",
    "precipitation_probability_max": "precipitation_probability_max",
    "wind_speed_10m_max": "wind_speed_max",
    "wind_gusts_10m_max": "wind_gusts_max",
    "wind_direction_10m_dominant": "wind_direction_dominant",
}


class WeatherServiceError(RuntimeError):
    """Raised when weather data cannot be requested or validated."""


def _request_json(url, params, headers=None, expected_type=dict):
    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        raise WeatherServiceError(
            "Der Wetterdienst ist momentan nicht erreichbar."
        ) from error

    if not isinstance(payload, expected_type):
        raise WeatherServiceError(
            "Der Wetterdienst hat ungültige Daten geliefert."
        )

    if isinstance(payload, dict) and payload.get("error"):
        reason = payload.get("reason") if isinstance(payload, dict) else None
        raise WeatherServiceError(
            str(reason or "Der Wetterdienst hat ungültige Daten geliefert.")
        )

    return payload


def _postal_location_name(address, result):
    for key in (
        "city_district",
        "suburb",
        "quarter",
        "neighbourhood",
        "city",
        "town",
        "village",
        "municipality",
    ):
        if address.get(key):
            return str(address[key])
    return str(result.get("display_name") or result.get("name") or "PLZ-Gebiet")


def _postal_city_name(address):
    for key in ("city", "town", "village", "municipality"):
        if address.get(key):
            return str(address[key])
    return ""


def search_german_postal_code(postal_code, count=8):
    payload = _request_json(
        POSTAL_GEOCODING_URL,
        {
            "postalcode": postal_code,
            "countrycodes": "de",
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": max(1, min(int(count), 10)),
            "accept-language": "de",
        },
        headers={
            "User-Agent": "MONOLITH/1.0 (self-hosted weather dashboard)",
        },
        expected_type=list,
    )

    locations = []
    for result in payload:
        address = result.get("address") or {}
        result_postal_code = str(address.get("postcode") or result.get("name") or "")
        if (
            result_postal_code != postal_code
            or str(address.get("country_code") or "").lower() != "de"
        ):
            continue
        try:
            provider_location_id = (
                NOMINATIM_LOCATION_ID_OFFSET
                + int(result["place_id"])
            )
            latitude = float(result["lat"])
            longitude = float(result["lon"])
        except (KeyError, TypeError, ValueError):
            continue

        locations.append({
            "provider_location_id": provider_location_id,
            "geocoding_provider": "nominatim",
            "postal_code": postal_code,
            "name": _postal_location_name(address, result),
            "city": _postal_city_name(address),
            "admin1": address.get("state") or "",
            "country": address.get("country") or "Deutschland",
            "country_code": "DE",
            "latitude": latitude,
            "longitude": longitude,
            "elevation": None,
            "timezone": "auto",
        })

    return locations


def search_locations(query, count=8):
    normalized_query = str(query or "").strip()
    if len(normalized_query) < 2:
        return []

    postal_match = GERMAN_POSTAL_CODE_PATTERN.fullmatch(normalized_query)
    if postal_match:
        return search_german_postal_code(postal_match.group(1), count)
    if normalized_query.isdigit():
        return []

    payload = _request_json(
        GEOCODING_URL,
        {
            "name": normalized_query[:80],
            "count": max(1, min(int(count), 10)),
            "language": "de",
            "format": "json",
        },
    )

    locations = []
    for result in payload.get("results", []):
        if not all(key in result for key in ("id", "name", "latitude", "longitude")):
            continue
        locations.append({
            "provider_location_id": int(result["id"]),
            "geocoding_provider": "open_meteo",
            "postal_code": "",
            "name": str(result["name"]),
            "city": str(result["name"]),
            "admin1": result.get("admin1") or "",
            "country": result.get("country") or "",
            "country_code": result.get("country_code") or "",
            "latitude": float(result["latitude"]),
            "longitude": float(result["longitude"]),
            "elevation": result.get("elevation"),
            "timezone": result.get("timezone") or "auto",
        })

    return locations


def _normalize_current(current):
    if not isinstance(current, dict) or not current.get("time"):
        return None
    row = {"time": current["time"], "source": "current"}
    for provider_name, stored_name in HOURLY_NAMES.items():
        row[stored_name] = current.get(provider_name)
    return row


def _normalize_timeseries(section, names, output_key):
    if not isinstance(section, dict):
        return []
    timestamps = section.get("time")
    if not isinstance(timestamps, list):
        return []

    rows = []
    for index, timestamp in enumerate(timestamps):
        row = {output_key: timestamp}
        for provider_name, stored_name in names.items():
            values = section.get(provider_name, [])
            row[stored_name] = (
                values[index]
                if isinstance(values, list) and index < len(values)
                else None
            )
        rows.append(row)
    return rows


def fetch_weather(latitude, longitude, timezone="auto"):
    payload = _request_json(
        FORECAST_URL,
        {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "timezone": timezone or "auto",
            "current": ",".join(CURRENT_FIELDS),
            "hourly": ",".join(HOURLY_FIELDS),
            "daily": ",".join(DAILY_FIELDS),
            "past_days": 7,
            "forecast_days": 10,
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        },
    )

    current = _normalize_current(payload.get("current"))
    hourly = _normalize_timeseries(
        payload.get("hourly"),
        HOURLY_NAMES,
        "time",
    )
    daily = _normalize_timeseries(
        payload.get("daily"),
        DAILY_NAMES,
        "date",
    )

    today = (
        current["time"][:10]
        if current and current.get("time")
        else date.today().isoformat()
    )
    for row in hourly:
        row["source"] = "history" if row["time"][:10] < today else "forecast"
    for row in daily:
        row["source"] = "history" if row["date"] < today else "forecast"

    if current is None or not hourly or not daily:
        raise WeatherServiceError(
            "Der Wetterdienst hat keine vollständigen Daten geliefert."
        )

    return {
        "current": current,
        "hourly": hourly,
        "daily": daily,
        "timezone": payload.get("timezone") or timezone,
        "timezone_abbreviation": payload.get("timezone_abbreviation"),
        "utc_offset_seconds": payload.get("utc_offset_seconds", 0),
        "elevation": payload.get("elevation"),
    }
