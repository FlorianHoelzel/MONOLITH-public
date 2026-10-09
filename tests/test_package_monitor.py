import unittest
from unittest.mock import patch

from monolith import package_monitor


class PackageMonitorTest(unittest.TestCase):
    @patch("monolith.package_monitor.save_event")
    @patch("monolith.package_monitor.sync_package_tracking")
    @patch("monolith.package_monitor.fetch_ship24_tracking")
    @patch("monolith.package_monitor.track_ship24_shipment")
    @patch("monolith.package_monitor.set_package_tracker")
    @patch("monolith.package_monitor.register_ship24_tracker")
    @patch("monolith.package_monitor.get_packages_for_sync")
    @patch("monolith.package_monitor.ship24_is_configured")
    def test_registers_and_refreshes_active_package(
        self,
        configured,
        get_packages,
        register,
        set_tracker,
        live_track,
        fetch,
        sync,
        save_event,
    ):
        configured.return_value = True
        get_packages.return_value = [{
            "id": 4,
            "name": "Kamera",
            "tracking_number": "123456789012",
            "carrier": "dhl",
            "destination_post_code": "50667",
            "ship24_tracker_id": None,
            "ship24_courier_hint_applied": False,
            "status": "announced",
        }]
        register.return_value = "tracker-4"
        live_track.return_value = {
            "tracker_id": "tracker-4",
            "used_per_call": False,
            "status": "in_transit",
            "expected_delivery": "2026-09-28",
            "events": [{
                "event_id": "event-1",
                "status": "in_transit",
                "detail": "Unterwegs",
                "location": "Köln",
                "occurred_at": 1790490600,
            }],
        }

        result = package_monitor.refresh_packages()

        self.assertEqual(result["updated"], 1)
        get_packages.assert_called_once_with(
            None,
            refresh_interval_seconds=(
                package_monitor.PACKAGE_REFRESH_INTERVAL_SECONDS
            ),
            urgent_refresh_interval_seconds=(
                package_monitor.PACKAGE_URGENT_REFRESH_INTERVAL_SECONDS
            ),
        )
        register.assert_not_called()
        set_tracker.assert_called_once_with(
            4,
            "tracker-4",
            courier_hint_applied=True,
        )
        live_track.assert_called_once()
        fetch.assert_not_called()
        sync.assert_called_once()
        save_event.assert_called_once()

    @patch("monolith.package_monitor.save_event")
    @patch("monolith.package_monitor.sync_package_tracking")
    @patch("monolith.package_monitor.fetch_ship24_tracking")
    @patch("monolith.package_monitor.get_packages_for_sync")
    @patch("monolith.package_monitor.ship24_is_configured")
    def test_empty_background_result_does_not_regress_status(
        self,
        configured,
        get_packages,
        fetch,
        sync,
        save_event,
    ):
        configured.return_value = True
        get_packages.return_value = [{
            "id": 9,
            "name": "Paket",
            "tracking_number": "123456789012",
            "carrier": "dhl",
            "destination_post_code": "12345",
            "ship24_tracker_id": "tracker-9",
            "ship24_courier_hint_applied": True,
            "status": "in_transit",
        }]
        fetch.return_value = {
            "status": "announced",
            "expected_delivery": None,
            "events": [],
        }

        package_monitor.refresh_packages()

        self.assertEqual(sync.call_args.args[1], "in_transit")
        save_event.assert_not_called()

    @patch("monolith.package_monitor.ship24_is_configured")
    def test_skips_refresh_without_api_key(self, configured):
        configured.return_value = False

        result = package_monitor.refresh_packages()

        self.assertFalse(result["configured"])
        self.assertEqual(result["updated"], 0)

    @patch("monolith.package_monitor.get_packages_for_sync")
    @patch("monolith.package_monitor.ship24_is_configured")
    def test_manual_refresh_bypasses_due_filter(self, configured, get_packages):
        configured.return_value = True
        get_packages.return_value = []

        package_monitor.refresh_packages(17)

        get_packages.assert_called_once_with(
            17,
            refresh_interval_seconds=None,
            urgent_refresh_interval_seconds=None,
        )

    @patch("monolith.package_monitor.fetch_ship24_tracking")
    @patch("monolith.package_monitor.track_ship24_shipment")
    @patch("monolith.package_monitor.get_packages_for_sync")
    @patch("monolith.package_monitor.ship24_is_configured")
    def test_forced_live_refresh_bypasses_due_filter(
        self,
        configured,
        get_packages,
        live_track,
        fetch,
    ):
        configured.return_value = True
        get_packages.return_value = []

        package_monitor.refresh_packages(force=True, live=True)

        get_packages.assert_called_once_with(
            None,
            refresh_interval_seconds=None,
            urgent_refresh_interval_seconds=None,
        )
        live_track.assert_not_called()
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
