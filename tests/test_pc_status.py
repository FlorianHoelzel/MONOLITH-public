import unittest
import json
from unittest.mock import Mock, patch

from monolith import pc_status


class PcStatusTests(unittest.TestCase):
    def setUp(self):
        configuration = patch.object(pc_status, "PC_IP", "192.0.2.10")
        configuration.start()
        self.addCleanup(configuration.stop)

    def make_monitor(self):
        return pc_status.PcStatusMonitor(Mock())

    @patch("monolith.pc_status.socket.create_connection")
    def test_agent_port_online_is_authoritative(self, create_connection):
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        create_connection.return_value = connection
        monitor = self.make_monitor()
        monitor.connect_fritzbox = Mock()

        status = monitor.read_status()

        self.assertTrue(status)
        monitor.connect_fritzbox.assert_not_called()

    @patch(
        "monolith.pc_status.socket.create_connection",
        side_effect=TimeoutError,
    )
    def test_agent_port_offline_overrides_stale_fritz_status(
        self,
        _create_connection,
    ):
        monitor = self.make_monitor()
        monitor.fritz_hosts = Mock()
        monitor.fritz_hosts.get_host_status.return_value = True

        status = monitor.read_status()

        self.assertFalse(status)
        monitor.fritz_hosts.get_host_status.assert_not_called()

    @patch("monolith.pc_status.urllib.request.urlopen")
    def test_reads_authenticated_media_status(self, urlopen):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({
            "available": True,
            "session_active": True,
            "playing": True,
            "title": "Testtitel",
        }).encode("utf-8")
        urlopen.return_value = response
        monitor = self.make_monitor()

        with patch.object(
            pc_status,
            "PC_AGENT_TOKEN",
            "test-token",
        ):
            status = monitor.read_media_status()

        self.assertTrue(status["session_active"])
        self.assertEqual(status["title"], "Testtitel")
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.get_header("X-pc-token"),
            "test-token",
        )


if __name__ == "__main__":
    unittest.main()
