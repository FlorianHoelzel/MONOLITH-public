import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monolith import database
from monolith import weather


def make_weather_payload():
    current = {
        "time": "2026-09-28T12:15",
        "temperature_2m": 16.4,
        "apparent_temperature": 15.7,
        "relative_humidity_2m": 71,
        "precipitation_probability": 20,
        "precipitation": 0.0,
        "rain": 0.0,
        "showers": 0.0,
        "snowfall": 0.0,
        "weather_code": 2,
        "cloud_cover": 54,
        "pressure_msl": 1016.2,
        "surface_pressure": 1008.1,
        "wind_speed_10m": 12.4,
        "wind_direction_10m": 245,
        "wind_gusts_10m": 21.3,
        "visibility": 24000,
        "uv_index": 2.1,
        "is_day": 1,
    }
    hourly = {"time": ["2026-09-27T12:00", "2026-09-28T13:00"]}
    for field in weather.HOURLY_FIELDS:
        value = current[field]
        hourly[field] = [value, value]
    daily = {"time": ["2026-09-27", "2026-09-28"]}
    for field in weather.DAILY_FIELDS:
        if field == "sunrise":
            daily[field] = ["2026-09-27T07:20", "2026-09-28T07:22"]
        elif field == "sunset":
            daily[field] = ["2026-09-27T19:13", "2026-09-28T19:10"]
        else:
            daily[field] = [2, 3]
    return {
        "current": current,
        "hourly": hourly,
        "daily": daily,
        "timezone": "Europe/Berlin",
        "timezone_abbreviation": "CEST",
        "utc_offset_seconds": 7200,
        "elevation": 55,
    }


class WeatherClientTests(unittest.TestCase):
    @patch("monolith.weather._request_json")
    def test_forecast_is_normalized_into_history_and_forecast(self, request_json):
        request_json.return_value = make_weather_payload()

        result = weather.fetch_weather(50.94, 6.96, "Europe/Berlin")

        self.assertEqual(result["current"]["temperature"], 16.4)
        self.assertEqual(result["hourly"][0]["source"], "history")
        self.assertEqual(result["hourly"][1]["source"], "forecast")
        self.assertEqual(result["daily"][0]["date"], "2026-09-27")
        self.assertEqual(result["daily"][1]["temperature_max"], 3)

    @patch("monolith.weather._request_json")
    def test_location_search_returns_only_required_public_fields(self, request_json):
        request_json.return_value = {
            "results": [{
                "id": 2886242,
                "name": "Köln",
                "latitude": 50.9333,
                "longitude": 6.95,
                "elevation": 58,
                "timezone": "Europe/Berlin",
                "country": "Deutschland",
                "country_code": "DE",
                "admin1": "Nordrhein-Westfalen",
                "population": 999999,
            }]
        }

        locations = weather.search_locations("Köln")

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0]["provider_location_id"], 2886242)
        self.assertEqual(locations[0]["geocoding_provider"], "open_meteo")
        self.assertEqual(locations[0]["postal_code"], "")
        self.assertNotIn("population", locations[0])

    @patch("monolith.weather._request_json")
    def test_five_digit_postal_code_uses_exact_german_postal_area(self, request_json):
        request_json.return_value = [{
            "place_id": 123456789,
            "lat": "52.53",
            "lon": "13.38",
            "display_name": "10115, Berlin, Deutschland",
            "address": {
                "postcode": "10115",
                "suburb": "Mitte",
                "city": "Berlin",
                "country": "Deutschland",
                "country_code": "de",
            },
        }]

        locations = weather.search_locations("10115 Berlin")

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0]["name"], "Mitte")
        self.assertEqual(locations[0]["city"], "Berlin")
        self.assertEqual(locations[0]["postal_code"], "10115")
        self.assertEqual(locations[0]["geocoding_provider"], "nominatim")
        self.assertAlmostEqual(locations[0]["latitude"], 52.53)
        self.assertAlmostEqual(locations[0]["longitude"], 13.38)
        request_url, request_params = request_json.call_args.args
        self.assertEqual(request_url, weather.POSTAL_GEOCODING_URL)
        self.assertEqual(request_params["postalcode"], "10115")
        self.assertEqual(request_params["countrycodes"], "de")
        self.assertIs(request_json.call_args.kwargs["expected_type"], list)

    @patch("monolith.weather._request_json")
    def test_incomplete_numeric_postal_code_does_not_call_provider(self, request_json):
        self.assertEqual(weather.search_locations("5066"), [])
        request_json.assert_not_called()


class WeatherDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        database.DATABASE_PATH = (
            Path(self.temporary_directory.name) / "monolith-test.db"
        )
        database.init_database()

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def test_location_and_weather_series_round_trip(self):
        location = database.set_weather_location({
            "provider_location_id": 2886242,
            "geocoding_provider": "nominatim",
            "postal_code": "50667",
            "name": "Köln",
            "city": "Köln",
            "admin1": "Nordrhein-Westfalen",
            "country": "Deutschland",
            "country_code": "DE",
            "latitude": 50.9333,
            "longitude": 6.95,
            "elevation": 58,
            "timezone": "Europe/Berlin",
        })
        with patch("monolith.weather._request_json", return_value=make_weather_payload()):
            weather_data = weather.fetch_weather(
                location["latitude"],
                location["longitude"],
                location["timezone"],
            )

        database.save_weather_data(location["id"], weather_data)
        stored = database.get_weather_data(location["id"])
        selected = database.get_selected_weather_location()

        self.assertEqual(selected["name"], "Köln")
        self.assertEqual(selected["postal_code"], "50667")
        self.assertEqual(selected["city"], "Köln")
        self.assertEqual(selected["geocoding_provider"], "nominatim")
        self.assertEqual(stored["current"]["temperature"], 16.4)
        self.assertEqual(len(stored["hourly"]), 2)
        self.assertEqual(stored["daily"][1]["date"], "2026-09-28")
        self.assertIsNotNone(selected["last_synced_at"])

    def test_selecting_another_location_replaces_selection(self):
        base = {
            "admin1": "",
            "country": "Deutschland",
            "country_code": "DE",
            "latitude": 50.0,
            "longitude": 7.0,
            "elevation": 50,
            "timezone": "Europe/Berlin",
        }
        database.set_weather_location({
            **base,
            "provider_location_id": 1,
            "name": "Ort Eins",
        })
        database.set_weather_location({
            **base,
            "provider_location_id": 2,
            "name": "Ort Zwei",
        })

        selected = database.get_selected_weather_location()

        self.assertEqual(selected["provider_location_id"], 2)

    def test_existing_weather_location_table_receives_city_column(self):
        database.DATABASE_PATH.unlink()
        connection = sqlite3.connect(database.DATABASE_PATH)
        connection.execute(
            """
            CREATE TABLE weather_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_location_id INTEGER NOT NULL UNIQUE,
                geocoding_provider TEXT NOT NULL DEFAULT 'open_meteo',
                postal_code TEXT,
                name TEXT NOT NULL,
                admin1 TEXT,
                country TEXT,
                country_code TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                elevation REAL,
                timezone TEXT NOT NULL,
                is_selected INTEGER NOT NULL DEFAULT 0,
                last_synced_at INTEGER,
                last_sync_error TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO weather_locations (
                provider_location_id, geocoding_provider, postal_code, name,
                country, country_code, latitude, longitude, timezone,
                is_selected, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                weather.NOMINATIM_LOCATION_ID_OFFSET + 1,
                "nominatim",
                "10115",
                "Berlin",
                "Deutschland",
                "DE",
                52.53,
                13.38,
                "auto",
                1,
                1,
            ),
        )
        connection.commit()
        connection.close()

        database.init_database()
        migrated = database.get_selected_weather_location()

        self.assertIn("city", migrated)
        self.assertIsNone(migrated["city"])
        self.assertEqual(migrated["name"], "Berlin")


class WeatherApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.import_directory = tempfile.TemporaryDirectory()
        cls.original_database_path = database.DATABASE_PATH
        database.DATABASE_PATH = Path(cls.import_directory.name) / "import.db"
        from monolith import app as app_module
        cls.app_module = app_module

    @classmethod
    def tearDownClass(cls):
        database.DATABASE_PATH = cls.original_database_path
        cls.import_directory.cleanup()

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.temporary_directory.name) / "api.db"
        database.init_database()
        self.client = self.app_module.app.test_client()
        with patch("monolith.weather._request_json", return_value=make_weather_payload()):
            self.normalized_weather = weather.fetch_weather(
                50.9333,
                6.95,
                "Europe/Berlin",
            )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_unconfigured_weather_endpoint_has_an_empty_state(self):
        response = self.client.get("/api/weather")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["configured"])

    def test_selecting_location_returns_and_caches_weather(self):
        location = {
            "provider_location_id": weather.NOMINATIM_LOCATION_ID_OFFSET + 123456789,
            "geocoding_provider": "nominatim",
            "postal_code": "50667",
            "name": "Köln",
            "city": "Köln",
            "admin1": "Nordrhein-Westfalen",
            "country": "Deutschland",
            "country_code": "DE",
            "latitude": 50.9333,
            "longitude": 6.95,
            "elevation": 58,
            "timezone": "Europe/Berlin",
        }
        with patch.object(
            self.app_module,
            "fetch_weather",
            return_value=self.normalized_weather,
        ) as fetch_weather:
            selected = self.client.post("/api/weather/location", json=location)

        cached = self.client.get("/api/weather")

        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.get_json()["current"]["temperature"], 16.4)
        self.assertEqual(cached.status_code, 200)
        self.assertEqual(cached.get_json()["location"]["name"], "Köln")
        self.assertEqual(cached.get_json()["location"]["postal_code"], "50667")
        self.assertEqual(cached.get_json()["location"]["city"], "Köln")
        self.assertEqual(
            cached.get_json()["location"]["geocoding_provider"],
            "nominatim",
        )
        self.assertEqual(fetch_weather.call_count, 1)

    def test_existing_postal_selection_refreshes_district_metadata(self):
        provider_location_id = weather.NOMINATIM_LOCATION_ID_OFFSET + 123456789
        database.set_weather_location({
            "provider_location_id": provider_location_id,
            "geocoding_provider": "nominatim",
            "postal_code": "10115",
            "name": "Berlin",
            "admin1": "",
            "country": "Deutschland",
            "country_code": "DE",
            "latitude": 52.53,
            "longitude": 13.38,
            "elevation": None,
            "timezone": "auto",
        })
        refreshed_location = {
            "provider_location_id": provider_location_id,
            "geocoding_provider": "nominatim",
            "postal_code": "10115",
            "name": "Mitte",
            "city": "Berlin",
            "admin1": "",
            "country": "Deutschland",
            "country_code": "DE",
            "latitude": 52.53,
            "longitude": 13.38,
            "elevation": None,
            "timezone": "auto",
        }

        with (
            patch.object(
                self.app_module,
                "search_locations",
                return_value=[refreshed_location],
            ) as search_locations,
            patch.object(
                self.app_module,
                "fetch_weather",
                return_value=self.normalized_weather,
            ),
        ):
            response = self.client.get("/api/weather?refresh=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["location"]["name"], "Mitte")
        self.assertEqual(response.get_json()["location"]["city"], "Berlin")
        search_locations.assert_called_once_with("10115")


if __name__ == "__main__":
    unittest.main()
