import tempfile
import unittest
import sqlite3
from pathlib import Path
from unittest.mock import patch

from monolith import database
from monolith.package_tracking import (
    carrier_details,
    detect_carrier,
    fetch_ship24_tracking,
    normalize_tracking_number,
    register_ship24_tracker,
    track_ship24_shipment,
)


class PackageTrackingTest(unittest.TestCase):
    def test_normalizes_tracking_numbers(self):
        self.assertEqual(
            normalize_tracking_number(" 1z 999 aa1 01 2345 6784 "),
            "1Z999AA10123456784",
        )

    def test_detects_distinct_carrier_formats(self):
        cases = {
            "1Z999AA10123456784": "ups",
            "TBA123456789012": "amazon",
            "RR123456789DE": "deutsche_post",
            "JJD012345678901234567": "dhl",
            "12345678901234": "hermes",
            "12345678901": "dpd",
            "12345678": "gls",
            "123456789012": "fedex",
            "123456789": "tnt",
        }

        for number, carrier in cases.items():
            with self.subTest(number=number):
                self.assertEqual(detect_carrier(number), carrier)

    def test_builds_encoded_official_tracking_link(self):
        details = carrier_details(
            "ups",
            "1Z 999 AA1 01 2345 6784",
        )
        self.assertEqual(details["name"], "UPS")
        self.assertIn("1Z999AA10123456784", details["tracking_url"])

    @patch("monolith.package_tracking._ship24_request")
    def test_registers_ship24_tracker(self, request):
        request.return_value = {
            "data": {
                "tracker": {
                    "trackerId": "tracker-123",
                }
            }
        }

        tracker_id = register_ship24_tracker(
            "1Z999AA10123456784",
            "monolith-package-7",
            "Kopfhörer",
            "50667",
            "dhl",
        )

        self.assertEqual(tracker_id, "tracker-123")
        payload = request.call_args.kwargs["json"]
        self.assertEqual(payload["destinationCountryCode"], "DE")
        self.assertEqual(payload["destinationPostCode"], "50667")
        self.assertEqual(payload["courierCode"], ["dhl"])

    @patch("monolith.package_tracking._ship24_request")
    def test_normalizes_ship24_tracking_result(self, request):
        request.return_value = {
            "data": {
                "trackings": [{
                    "shipment": {
                        "statusMilestone": "out_for_delivery",
                        "delivery": {
                            "courierEstimatedDeliveryDate": {
                                "from": "2026-09-27T10:00:00+02:00",
                            }
                        },
                    },
                    "events": [{
                        "eventId": "event-1",
                        "status": "In Zustellung",
                        "statusMilestone": "out_for_delivery",
                        "occurrenceDatetime": "2026-09-27T08:30:00+02:00",
                        "location": "Köln",
                    }],
                }]
            }
        }

        tracking = fetch_ship24_tracking("tracker-123")

        self.assertEqual(tracking["status"], "out_for_delivery")
        self.assertEqual(tracking["expected_delivery"], "2026-09-27")
        self.assertEqual(tracking["events"][0]["event_id"], "event-1")
        self.assertEqual(tracking["events"][0]["location"], "Köln")

    @patch("monolith.package_tracking._ship24_request")
    def test_synchronously_tracks_existing_shipment(self, request):
        request.return_value = {
            "data": {
                "trackings": [{
                    "tracker": {"trackerId": "tracker-live"},
                    "shipment": {"statusMilestone": "in_transit"},
                    "events": [{
                        "eventId": "event-live",
                        "status": "In der Region angekommen",
                        "statusMilestone": "in_transit",
                        "occurrenceDatetime": "2026-10-01T12:00:00+02:00",
                    }],
                }],
            },
        }

        tracking = track_ship24_shipment(
            "00340000000000000000",
            "monolith-package-3",
            "Testpaket",
            "12345",
            "dhl",
        )

        self.assertEqual(tracking["tracker_id"], "tracker-live")
        self.assertEqual(tracking["status"], "in_transit")
        self.assertFalse(tracking["used_per_call"])
        request.assert_called_once_with(
            "POST",
            "/trackers/track",
            json={
                "trackingNumber": "00340000000000000000",
                "clientTrackerId": "monolith-package-3",
                "shipmentReference": "monolith-package-3",
                "destinationCountryCode": "DE",
                "title": "Testpaket",
                "destinationPostCode": "12345",
                "courierCode": ["dhl"],
            },
            timeout=75,
        )

    @patch("monolith.package_tracking._ship24_request")
    def test_live_tracking_falls_back_to_per_call_when_tracker_is_empty(
        self,
        request,
    ):
        request.side_effect = [
            {
                "data": {
                    "trackings": [{
                        "tracker": {"trackerId": "tracker-empty"},
                        "shipment": {"statusMilestone": "info_received"},
                        "events": [],
                    }],
                },
            },
            {
                "data": {
                    "trackings": [{
                        "shipment": {"statusMilestone": "in_transit"},
                        "events": [{
                            "eventId": "event-direct",
                            "status": "In der Region angekommen",
                            "statusMilestone": "in_transit",
                            "occurrenceDatetime": (
                                "2026-10-01T12:00:00+02:00"
                            ),
                        }],
                    }],
                },
            },
        ]

        tracking = track_ship24_shipment(
            "00340000000000000000",
            "monolith-package-3",
            "Testpaket",
            "12345",
            "dhl",
        )

        self.assertTrue(tracking["used_per_call"])
        self.assertEqual(tracking["tracker_id"], "tracker-empty")
        self.assertEqual(tracking["events"][0]["event_id"], "event-direct")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[1].args, (
            "POST",
            "/tracking/search",
        ))
        self.assertEqual(
            request.call_args_list[1].kwargs["json"],
            {
                "trackingNumber": "00340000000000000000",
                "destinationCountryCode": "DE",
                "destinationPostCode": "12345",
                "courierCode": ["dhl"],
            },
        )

    @patch("monolith.package_tracking._ship24_request")
    def test_uses_latest_event_across_all_tracking_results(self, request):
        request.return_value = {
            "data": {
                "trackings": [
                    {
                        "shipment": {"statusMilestone": "info_received"},
                        "events": [{
                            "eventId": "old-event",
                            "status": "Elektronisch angekündigt",
                            "statusMilestone": "info_received",
                            "occurrenceDatetime": "2026-09-24T15:20:00+02:00",
                        }],
                    },
                    {
                        "shipment": {"statusMilestone": "failed_attempt"},
                        "events": [{
                            "eventId": "latest-event",
                            "status": "Zustellung heute nicht möglich",
                            "statusMilestone": "failed_attempt",
                            "occurrenceDatetime": "2026-09-25T16:48:00+02:00",
                        }],
                    },
                ]
            }
        }

        tracking = fetch_ship24_tracking("tracker-123")

        self.assertEqual(tracking["status"], "failed_attempt")
        self.assertEqual(tracking["events"][0]["event_id"], "latest-event")


class PackageDatabaseTest(unittest.TestCase):
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

    def test_package_lifecycle_keeps_status_history(self):
        package_id = database.create_package(
            "Kopfhörer",
            "1Z999AA10123456784",
            "ups",
            "announced",
            "2026-09-27",
            "Ablageort Haustür",
        )

        packages = database.get_packages()
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0]["id"], package_id)
        self.assertEqual(packages[0]["history"][0]["status"], "announced")

        updated = database.update_package(
            package_id,
            "in_transit",
            "2026-09-27",
            "Ablageort Haustür",
        )
        self.assertTrue(updated)

        package = database.get_packages()[0]
        self.assertEqual(package["status"], "in_transit")
        self.assertEqual(
            [item["status"] for item in package["history"]],
            ["in_transit", "announced"],
        )

        self.assertTrue(database.delete_package(package_id))
        self.assertEqual(database.get_packages(), [])

    def test_provider_sync_is_automatic_and_idempotent(self):
        package_id = database.create_package(
            "Kamera",
            "123456789012",
            "fedex",
            "announced",
            destination_post_code="50667",
        )
        database.set_package_tracker(package_id, "tracker-123")
        event = {
            "event_id": "provider-event-1",
            "status": "in_transit",
            "detail": "Im Paketzentrum bearbeitet",
            "location": "Köln",
            "occurred_at": 1790490600,
        }

        database.sync_package_tracking(
            package_id,
            "in_transit",
            "2026-09-28",
            [event],
        )
        database.sync_package_tracking(
            package_id,
            "in_transit",
            "2026-09-28",
            [event],
        )

        package = database.get_packages()[0]
        provider_events = [
            item
            for item in package["history"]
            if item["detail"] == "Im Paketzentrum bearbeitet"
        ]
        self.assertEqual(package["status"], "in_transit")
        self.assertEqual(package["expected_delivery"], "2026-09-28")
        self.assertEqual(package["ship24_tracker_id"], "tracker-123")
        self.assertEqual(len(provider_events), 1)

    def test_scheduled_sync_only_returns_due_packages(self):
        current_time = 2_000_000_000
        regular_due = database.create_package(
            "Regulär fällig",
            "regular-due-123",
            "other",
            "in_transit",
        )
        regular_recent = database.create_package(
            "Regulär aktuell",
            "regular-recent-123",
            "other",
            "in_transit",
        )
        urgent_due = database.create_package(
            "Dringend fällig",
            "urgent-due-123",
            "other",
            "out_for_delivery",
        )
        urgent_recent = database.create_package(
            "Dringend aktuell",
            "urgent-recent-123",
            "other",
            "failed_attempt",
        )

        connection = database.get_connection()
        connection.executemany(
            "UPDATE packages SET last_synced_at = ? WHERE id = ?",
            [
                (current_time - 901, regular_due),
                (current_time - 899, regular_recent),
                (current_time - 301, urgent_due),
                (current_time - 299, urgent_recent),
            ],
        )
        connection.commit()
        connection.close()

        due = database.get_packages_for_sync(
            refresh_interval_seconds=900,
            urgent_refresh_interval_seconds=300,
            now=current_time,
        )

        self.assertEqual(
            {package["id"] for package in due},
            {regular_due, urgent_due},
        )

        manual = database.get_packages_for_sync(regular_recent)
        self.assertEqual([package["id"] for package in manual], [regular_recent])

    def test_unchanged_provider_sync_keeps_package_sort_timestamp(self):
        package_id = database.create_package(
            "Unverändert",
            "unchanged-123",
            "other",
            "in_transit",
        )
        connection = database.get_connection()
        connection.execute(
            "UPDATE packages SET updated_at = 1234 WHERE id = ?",
            (package_id,),
        )
        connection.commit()
        connection.close()

        database.sync_package_tracking(
            package_id,
            "in_transit",
            None,
            [],
        )

        connection = database.get_connection()
        row = connection.execute(
            "SELECT updated_at, last_synced_at FROM packages WHERE id = ?",
            (package_id,),
        ).fetchone()
        connection.close()
        self.assertEqual(row["updated_at"], 1234)
        self.assertIsNotNone(row["last_synced_at"])

    def test_existing_package_tables_receive_tracking_columns(self):
        database.DATABASE_PATH.unlink()
        connection = sqlite3.connect(database.DATABASE_PATH)
        connection.executescript(
            """
            CREATE TABLE packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tracking_number TEXT NOT NULL UNIQUE,
                carrier TEXT NOT NULL,
                status TEXT NOT NULL,
                expected_delivery TEXT,
                note TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE package_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                detail TEXT,
                created_at INTEGER NOT NULL
            );
            """
        )
        connection.close()

        database.init_database()

        connection = database.get_connection()
        package_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(packages)")
        }
        history_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(package_history)")
        }
        connection.close()
        self.assertIn("ship24_tracker_id", package_columns)
        self.assertIn("last_synced_at", package_columns)
        self.assertIn("ship24_courier_hint_applied", package_columns)
        self.assertIn("provider_event_id", history_columns)


if __name__ == "__main__":
    unittest.main()
