import unittest
from unittest.mock import Mock, patch

from monolith import lg_tv


class LgTvMonitorTests(unittest.IsolatedAsyncioTestCase):
    def test_repeated_connection_issue_is_logged_once(self):
        monitor = lg_tv.LgTvMonitor(Mock())

        with patch("builtins.print") as output:
            monitor._log_connection_issue(
                "standby",
                "TV ist im Netzwerk-Standby",
            )
            monitor._log_connection_issue(
                "standby",
                "TV ist im Netzwerk-Standby",
            )
            monitor._log_connection_issue(
                "error:OSError",
                "Verbindung nicht verfügbar",
            )

        self.assertEqual(output.call_count, 2)

    async def test_transient_disconnect_keeps_last_confirmed_power(self):
        statuses = []
        monitor = lg_tv.LgTvMonitor(statuses.append)
        monitor.has_connected = True
        monitor.last_power_value = True
        monitor.stop_event.set()

        class FailingClient:
            client_key = "paired"

            async def register_state_update_callback(self, _callback):
                return None

            async def connect(self):
                raise OSError("temporary websocket failure")

            async def disconnect(self):
                return None

        monitor._read_client_key = Mock(return_value="paired")

        original_client = lg_tv.LgWebOsClient
        lg_tv.LgWebOsClient = Mock(return_value=FailingClient())
        monitor.stop_event.clear()

        def stop_after_status(status):
            statuses.append(status)
            monitor.stop_event.set()

        monitor.on_status = stop_after_status

        try:
            await monitor._monitor_forever()
        finally:
            lg_tv.LgWebOsClient = original_client

        self.assertTrue(statuses[-1]["value"])
        self.assertFalse(statuses[-1]["connected"])


if __name__ == "__main__":
    unittest.main()
