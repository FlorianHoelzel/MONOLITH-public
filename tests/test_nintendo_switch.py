import unittest
from unittest.mock import Mock, patch

from monolith import nintendo_switch as switch


class SwitchStatusTests(unittest.TestCase):
    def setUp(self):
        configuration = patch.object(switch, "SWITCH_MAC", "02:00:00:00:00:01")
        configuration.start()
        self.addCleanup(configuration.stop)
        label = patch.dict(switch.devices["device_console_01"], {"name": "Testkonsole"})
        label.start()
        self.addCleanup(label.stop)

    @patch.object(switch, "FRITZBOX_ADDRESS", "router.test")
    @patch.object(switch, "FRITZBOX_USER", "test")
    @patch.object(switch, "FRITZBOX_PASSWORD", "test")
    @patch.object(switch, "FritzHosts")
    def test_queries_only_switch_mac_and_follows_dhcp(self, hosts):
        hosts.return_value.get_specific_host_entry.return_value = {
            "NewActive": True, "NewIPAddress": "192.0.2.99",
        }
        monitor = switch.SwitchMonitor()
        monitor.refresh()
        monitor.refresh()
        hosts.assert_called_once()
        self.assertEqual(hosts.call_args.kwargs["timeout"], 2)
        hosts.return_value.get_hosts_info.assert_not_called()
        hosts.return_value.get_specific_host_entry.assert_called_with(switch.SWITCH_MAC)
        self.assertEqual(monitor.get_status()["address"], "192.0.2.99")
        self.assertEqual(monitor.get_status()["value"], "An")

    def test_failure_keeps_state_then_expires_without_false_feed_events(self):
        events = Mock()
        monitor = switch.SwitchMonitor(events)
        monitor.read_status = Mock(return_value={"network_connected": True})
        with patch.object(switch.time, "monotonic", return_value=100):
            monitor.refresh()
        monitor.read_status.side_effect = TimeoutError()
        with patch.object(switch.time, "monotonic", return_value=105):
            monitor.refresh()
            self.assertEqual(monitor.get_status()["value"], "An")
            self.assertTrue(monitor.get_status()["status_stale"])
        with patch.object(switch.time, "monotonic", return_value=161):
            self.assertEqual(monitor.get_status()["value"], "Unbekannt")
            monitor.refresh()
        events.assert_not_called()
        monitor.read_status.side_effect = None
        with patch.object(switch.time, "monotonic", return_value=162):
            monitor.refresh()
            self.assertEqual(monitor.get_status()["value"], "An")
            self.assertFalse(monitor.get_status()["status_stale"])
        events.assert_not_called()

    def test_confirmed_off_is_immediate(self):
        monitor = switch.SwitchMonitor()
        monitor.read_status = Mock(return_value={"network_connected": True})
        monitor.refresh()
        monitor.read_status.return_value = {"network_connected": False}
        monitor.refresh()
        self.assertEqual(monitor.get_status()["value"], "Aus")

    def test_initial_failure_is_unknown(self):
        monitor = switch.SwitchMonitor()
        monitor.read_status = Mock(side_effect=TimeoutError())
        monitor.refresh()
        self.assertEqual(monitor.get_status()["value"], "Unbekannt")

    def test_feed_tracks_changes_without_startup_or_unknown_events(self):
        for states, expected in (
            ([True, True, False, False, True], ["Testkonsole ausgeschaltet", "Testkonsole eingeschaltet"]),
            ([False, True], ["Testkonsole eingeschaltet"]),
            ([True, None, True], []),
            ([True, None, False], ["Testkonsole ausgeschaltet"]),
            ([None, False, False], []),
        ):
            with self.subTest(states=states):
                events = Mock()
                monitor = switch.SwitchMonitor(events)
                monitor.read_status = Mock()
                for active in states:
                    monitor.read_status.return_value = {"network_connected": active}
                    monitor.refresh()
                self.assertEqual([call.kwargs["title"] for call in events.call_args_list], expected)
                for call in events.call_args_list:
                    self.assertEqual(call.kwargs["source_id"], "device_console_01")
                    self.assertEqual(call.kwargs["room"], switch.SWITCH_ROOM)


if __name__ == "__main__":
    unittest.main()
