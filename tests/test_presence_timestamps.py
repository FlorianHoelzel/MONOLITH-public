import os
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch


TEST_DATA_DIRECTORY = tempfile.TemporaryDirectory()
os.environ["MONOLITH_DATA_DIR"] = TEST_DATA_DIRECTORY.name


from monolith import database


database.init_database()


from monolith import presence


class PresenceTimestampTests(unittest.TestCase):
    def test_manual_home_survives_offline_until_device_returns(self):
        monitor = presence.PresenceMonitor.__new__(presence.PresenceMonitor)
        monitor.lock = threading.RLock()
        monitor.people_state = {"person_2": {
            "home": True, "last_seen": 99, "missing_since": None,
            "status_since": 10, "device_status": {},
            "manual_home_until_seen": True,
        }}
        monitor.save_presence_state = Mock()
        monitor.create_presence_event = Mock()
        monitor.get_person_device_status = Mock(return_value={
            "statuses": {}, "online_devices": [],
            "any_online": False, "has_unknown": False,
        })
        with patch.object(presence.time, "time", return_value=10000):
            monitor.process_person("person_2")
        state = monitor.people_state["person_2"]
        self.assertTrue(state["home"])
        self.assertEqual(state["status_since"], 10)
        self.assertIsNone(state["missing_since"])
        monitor.get_person_device_status.return_value.update(any_online=True)
        monitor.process_person("person_2")
        self.assertFalse(state["manual_home_until_seen"])
        self.assertEqual(state["status_since"], 10)
        monitor.get_person_device_status.return_value.update(any_online=False)
        monitor.process_person("person_2")
        self.assertIsNotNone(state["missing_since"])
        monitor.create_presence_event.assert_not_called()

    def setUp(self):
        connection = database.get_connection()
        connection.execute("DELETE FROM events")
        connection.commit()
        connection.close()

    def test_custom_event_time_controls_feed_order(self):
        database.save_event(
            event_type="test",
            title="Newer",
            created_at=200,
        )
        database.save_event(
            event_type="presence",
            title="Person 2 hat das Haus verlassen",
            created_at=100,
        )
        database.save_event(
            event_type="test",
            title="Older",
            created_at=50,
        )

        events = database.get_recent_events()

        self.assertEqual(
            [event["title"] for event in events],
            [
                "Newer",
                "Person 2 hat das Haus verlassen",
                "Older",
            ],
        )
        self.assertEqual(events[1]["timestamp"], 100)

    def test_confirmed_departure_uses_first_offline_time(self):
        monitor = presence.PresenceMonitor.__new__(
            presence.PresenceMonitor
        )
        monitor.lock = threading.RLock()
        monitor.people_state = {
            "person_2": {
                "home": True,
                "last_seen": 99,
                "missing_since": 100,
                "status_since": 10,
                "device_status": {},
            }
        }
        monitor.get_person_device_status = Mock(
            return_value={
                "statuses": {
                    "device_1": False,
                    "device_2": False,
                },
                "online_devices": [],
                "any_online": False,
                "has_unknown": False,
            }
        )
        monitor.save_presence_state = Mock()
        monitor.create_presence_event = Mock()

        original_time = presence.time.time
        presence.time.time = Mock(
            return_value=(
                100
                + presence.AWAY_AFTER_SECONDS
            )
        )

        try:
            monitor.process_person("person_2")
        finally:
            presence.time.time = original_time

        state = monitor.people_state["person_2"]
        self.assertFalse(state["home"])
        self.assertEqual(state["status_since"], 100)
        monitor.create_presence_event.assert_called_once_with(
            "person_2",
            False,
            100,
        )

    def test_departure_event_forwards_occurrence_time(self):
        monitor = presence.PresenceMonitor.__new__(
            presence.PresenceMonitor
        )

        with patch("monolith.presence.save_event") as save_event:
            monitor.create_presence_event(
                "person_2",
                False,
                100.9,
            )

        save_event.assert_called_once_with(
            event_type="presence",
            source_id="presence_person_2",
            room="Anwesenheit",
            title="Person 2 hat das Haus verlassen",
            created_at=100.9,
        )

    def test_short_device_dropout_does_not_mark_person_away(self):
        monitor = presence.PresenceMonitor.__new__(
            presence.PresenceMonitor
        )
        monitor.lock = threading.RLock()
        monitor.people_state = {
            "person_2": {
                "home": True,
                "last_seen": 99,
                "missing_since": 100,
                "status_since": 10,
                "device_status": {},
            }
        }
        monitor.get_person_device_status = Mock(
            return_value={
                "statuses": {
                    "device_1": False,
                    "device_2": False,
                },
                "online_devices": [],
                "any_online": False,
                "has_unknown": False,
            }
        )
        monitor.save_presence_state = Mock()
        monitor.create_presence_event = Mock()

        original_time = presence.time.time
        presence.time.time = Mock(
            return_value=100 + (10 * 60)
        )

        try:
            monitor.process_person("person_2")
        finally:
            presence.time.time = original_time

        self.assertTrue(
            monitor.people_state["person_2"]["home"]
        )
        monitor.create_presence_event.assert_not_called()

    def test_uncertain_check_restarts_departure_confirmation(self):
        monitor = presence.PresenceMonitor.__new__(presence.PresenceMonitor)
        monitor.lock = threading.RLock()
        monitor.people_state = {"person_2": {
            "home": True, "last_seen": 99, "missing_since": 100,
            "status_since": 10, "device_status": {},
        }}
        monitor.get_person_device_status = Mock(return_value={
            "statuses": {}, "online_devices": [],
            "any_online": False, "has_unknown": True,
        })
        monitor.save_presence_state = Mock()
        monitor.create_presence_event = Mock()
        with patch.object(presence.time, "time", return_value=10000):
            monitor.process_person("person_2")
            self.assertIsNone(monitor.people_state["person_2"]["missing_since"])
            monitor.get_person_device_status.return_value["has_unknown"] = False
            monitor.process_person("person_2")
        self.assertTrue(monitor.people_state["person_2"]["home"])
        self.assertEqual(monitor.people_state["person_2"]["missing_since"], 10000)
        monitor.create_presence_event.assert_not_called()

    def test_router_current_ip_replaces_outdated_configured_ip(self):
        monitor = presence.PresenceMonitor.__new__(presence.PresenceMonitor)
        monitor.fritz_hosts = Mock()
        monitor.get_router_hosts = Mock(return_value=[{
            "MACAddress": "02:00:00:00:00:0C", "Active": False,
            "IPAddress": "192.0.2.80",
        }])
        monitor.probe_device = Mock(return_value=True)
        self.assertTrue(monitor.get_device_status("02:00:00:00:00:0C", "192.0.2.76"))
        monitor.probe_device.assert_called_once_with("192.0.2.80", "02:00:00:00:00:0C")

    def test_router_mac_alias_can_confirm_presence(self):
        monitor = presence.PresenceMonitor.__new__(presence.PresenceMonitor)
        monitor.fritz_hosts = Mock()
        monitor.get_router_hosts = Mock(return_value=[{
            "MACAddress": "02:00:00:00:00:09", "Active": True,
            "X_AVM-DE_MACAddressList": "02:00:00:00:00:09,02:00:00:00:00:0c",
        }])
        monitor.probe_device = Mock()
        self.assertTrue(monitor.get_device_status("02:00:00:00:00:0C", "192.0.2.76"))
        monitor.probe_device.assert_not_called()

    def test_router_host_list_is_shared_for_polling_round(self):
        monitor = presence.PresenceMonitor.__new__(presence.PresenceMonitor)
        monitor.fritz_hosts = Mock()
        monitor.fritz_hosts.get_hosts_attributes.return_value = []
        with patch.object(presence.time, "monotonic", side_effect=[100, 101, 131]):
            monitor.get_router_hosts()
            monitor.get_router_hosts()
            self.assertEqual(monitor.fritz_hosts.get_hosts_attributes.call_count, 1)
            monitor.get_router_hosts()
        self.assertEqual(monitor.fritz_hosts.get_hosts_attributes.call_count, 2)

    def test_arp_confirms_matching_device_even_without_ping_reply(self):
        import json
        monitor = presence.PresenceMonitor
        for neighbor, expected in [
            ({"dst": "192.0.2.76", "lladdr": "02:00:00:00:00:0c", "state": ["REACHABLE"]}, True),
            ({"dst": "192.0.2.76", "lladdr": "02:00:00:00:00:0c", "state": ["STALE"]}, False),
            ({"dst": "192.0.2.76", "lladdr": "02:00:00:00:00:09", "state": ["REACHABLE"]}, False),
        ]:
            with self.subTest(neighbor=neighbor):
                with patch.object(presence.os, "name", "posix"), patch.object(
                    presence.subprocess, "run", side_effect=[
                        Mock(returncode=1), Mock(returncode=0, stdout=json.dumps([neighbor])),
                    ],
                ):
                    self.assertEqual(monitor.probe_device("192.0.2.76", "02:00:00:00:00:0C"), expected)

    def test_probe_tool_failure_is_unknown(self):
        with patch.object(presence.subprocess, "run", side_effect=FileNotFoundError):
            self.assertIsNone(presence.PresenceMonitor.probe_device("192.0.2.76", "02:00:00:00:00:0C"))

    def test_restart_discards_unobserved_offline_time(self):
        import json
        from pathlib import Path
        monitor = presence.PresenceMonitor.__new__(presence.PresenceMonitor)
        monitor.people_state = {"person_2": {}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "monolith.presence.json"
            path.write_text(json.dumps({"person_2": {
                "home": True, "status_since": 10, "missing_since": 100,
                "manual_home_until_seen": True,
            }}))
            with patch.object(presence, "STATE_FILE", path):
                self.assertTrue(monitor.restore_from_state_file())
        self.assertIsNone(monitor.people_state["person_2"]["missing_since"])
        self.assertTrue(monitor.people_state["person_2"]["manual_home_until_seen"])

    def test_direct_probe_overrides_stale_fritz_offline_status(self):
        monitor = presence.PresenceMonitor.__new__(
            presence.PresenceMonitor
        )
        monitor.fritz_hosts = Mock()
        monitor.get_router_hosts = Mock(return_value=[])
        monitor.fritz_hosts.get_specific_host_entry.return_value = {
            "NewActive": False, "NewIPAddress": "192.0.2.76",
        }
        monitor.probe_device = Mock(return_value=True)

        status = monitor.get_device_status(
            "02:00:00:00:00:0C",
            "192.0.2.76",
        )

        self.assertTrue(status)
        monitor.probe_device.assert_called_once_with(
            "192.0.2.76", "02:00:00:00:00:0C"
        )

    def test_failed_probe_keeps_confirmed_fritz_offline_status(self):
        monitor = presence.PresenceMonitor.__new__(
            presence.PresenceMonitor
        )
        monitor.fritz_hosts = Mock()
        monitor.get_router_hosts = Mock(return_value=[])
        monitor.fritz_hosts.get_specific_host_entry.return_value = {
            "NewActive": False, "NewIPAddress": "192.0.2.76",
        }
        monitor.probe_device = Mock(return_value=False)

        status = monitor.get_device_status(
            "02:00:00:00:00:0C",
            "192.0.2.76",
        )

        self.assertFalse(status)


if __name__ == "__main__":
    unittest.main()
