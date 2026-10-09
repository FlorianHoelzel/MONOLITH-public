import unittest
import json
import subprocess
from unittest.mock import mock_open, patch

from monolith import system_services


class SystemServicesTest(unittest.TestCase):
    def test_matterbridge_uses_deployed_unit_name(self):
        self.assertEqual(
            system_services.SERVICE_DEFINITIONS[2]["unit"],
            "robovac-matterbridge.service",
        )

    def test_parse_systemctl_output(self):
        result = system_services._parse_systemctl_output(
            "ActiveState=active\n"
            "MainPID=4321\n"
            "Description=Value=with=equals\n"
        )

        self.assertEqual(
            result["ActiveState"],
            "active",
        )
        self.assertEqual(
            result["MainPID"],
            "4321",
        )
        self.assertEqual(
            result["Description"],
            "Value=with=equals",
        )

    @patch(
        "monolith.system_services.open",
        mock_open(read_data="500.00 100.00"),
        create=True,
    )
    def test_service_payload_formats_active_service(self):
        payload = system_services._service_payload(
            system_services.SERVICE_DEFINITIONS[0],
            {
                "LoadState": "loaded",
                "ActiveState": "active",
                "SubState": "running",
                "MainPID": "4321",
                "MemoryCurrent": "1048576",
                "NRestarts": "2",
                "ActiveEnterTimestampMonotonic": "440000000",
            },
        )

        self.assertEqual(payload["state"], "active")
        self.assertEqual(payload["status_label"], "Aktiv")
        self.assertEqual(payload["pid"], 4321)
        self.assertEqual(payload["memory_bytes"], 1048576)
        self.assertEqual(payload["restart_count"], 2)
        self.assertEqual(payload["uptime_seconds"], 60)

    @patch(
        "monolith.system_services._read_process_memory_bytes",
        return_value=24 * 1024 * 1024,
    )
    def test_service_payload_falls_back_to_process_memory(
        self,
        read_memory,
    ):
        payload = system_services._service_payload(
            system_services.SERVICE_DEFINITIONS[0],
            {
                "LoadState": "loaded",
                "ActiveState": "active",
                "MainPID": "4321",
                "MemoryCurrent": "[not set]",
            },
        )

        self.assertEqual(
            payload["memory_bytes"],
            24 * 1024 * 1024,
        )
        read_memory.assert_called_once_with(4321)

    @patch(
        "monolith.system_services.open",
        mock_open(
            read_data=(
                "Name:\tpython\n"
                "VmPeak:\t  64000 kB\n"
                "VmRSS:\t   12345 kB\n"
            )
        ),
        create=True,
    )
    def test_process_memory_reads_resident_set(self):
        self.assertEqual(
            system_services._read_process_memory_bytes(
                4321
            ),
            12345 * 1024,
        )

    def test_not_found_unit_is_unavailable(self):
        payload = system_services._service_payload(
            system_services.SERVICE_DEFINITIONS[2],
            {
                "LoadState": "not-found",
                "ActiveState": "inactive",
            },
        )

        self.assertEqual(payload["state"], "unknown")
        self.assertEqual(
            payload["status_label"],
            "Nicht verfügbar",
        )

    @patch(
        "monolith.system_services.os.path.isdir",
        return_value=False,
    )
    @patch(
        "monolith.system_services.socket.gethostname",
        return_value="dev-machine",
    )
    def test_development_fallback_keeps_dashboard_active(
        self,
        _hostname,
        _isdir,
    ):
        result = system_services.get_system_services()

        self.assertEqual(result["source"], "development")
        self.assertEqual(result["summary"]["active"], 1)
        self.assertEqual(
            result["services"][0]["status_label"],
            "Entwicklung",
        )
        self.assertEqual(
            result["services"][1]["state"],
            "unknown",
        )

    def test_parse_journal_entry(self):
        entry = system_services._parse_journal_entry(
            json.dumps({
                "__CURSOR": "s=abc;i=12",
                "__REALTIME_TIMESTAMP": "1700000000000000",
                "_SYSTEMD_UNIT": "monolith.service",
                "PRIORITY": "4",
                "MESSAGE": "Verbindung getrennt",
            })
        )

        self.assertEqual(entry["service"], "MONOLITH")
        self.assertEqual(entry["priority"], 4)
        self.assertEqual(
            entry["message"],
            "Verbindung getrennt",
        )
        self.assertEqual(entry["cursor"], "s=abc;i=12")

    def test_journal_message_removes_ansi_colors(self):
        message = (
            "\x1b[0m\x1b[38;5;245m[18:24:58.623] "
            "\x1b[38;5;97m[Frontend]\x1b[0m connected\x1b[K"
        )

        self.assertEqual(
            system_services._normalize_journal_message(
                message
            ),
            "[18:24:58.623] [Frontend] connected",
        )

    def test_compact_logs_remove_purifier_sync_noise(self):
        entries = [
            {
                "timestamp": "2026-09-27T18:16:13+00:00",
                "message": "========== MONOLITH SYNC ==========",
            },
            {
                "timestamp": "2026-09-27T18:16:13+00:00",
                "message": "[sensor_hallway_pm25] Flur / pm25 -> 18",
            },
            {
                "timestamp": "2026-09-27T18:16:13+00:00",
                "message": "[device_air_filter_01_active] Air Purifier aktiv -> True",
            },
            {
                "timestamp": "2026-09-27T18:16:18+00:00",
                "message": "[device_air_filter_01_active] Air Purifier aktiv -> True",
            },
            {
                "timestamp": "2026-09-27T18:16:20+00:00",
                "message": "[ERROR] Verbindung verloren",
            },
        ]

        result = system_services._compact_journal_entries(
            entries
        )

        self.assertEqual(
            [entry["message"] for entry in result],
            [
                "[device_air_filter_01_active] Air Purifier aktiv -> True",
                "[ERROR] Verbindung verloren",
            ],
        )

    def test_compact_logs_dedupe_identical_lg_tv_noise(self):
        entries = [
            {
                "timestamp": "2026-09-27T18:16:13+00:00",
                "message": "[LG TV] Wohnzimmer / LG TV -> True · YouTube",
            },
            {
                "timestamp": "2026-09-27T18:16:18+00:00",
                "message": "[LG TV] Wohnzimmer / LG TV -> True · YouTube",
            },
            {
                "timestamp": "2026-09-27T18:16:20+00:00",
                "message": "[LG TV] Wohnzimmer / LG TV -> False",
            },
        ]

        result = system_services._compact_journal_entries(
            entries
        )

        self.assertEqual(
            [entry["message"] for entry in result],
            [
                "[LG TV] Wohnzimmer / LG TV -> True · YouTube",
                "[LG TV] Wohnzimmer / LG TV -> False",
            ],
        )

    @patch(
        "monolith.system_services.os.path.isdir",
        return_value=True,
    )
    @patch(
        "monolith.system_services.os.name",
        "posix",
    )
    @patch("monolith.system_services.subprocess.run")
    def test_logs_use_allowlisted_units_and_cursor(
        self,
        run,
        _isdir,
    ):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({
                "__CURSOR": "s=next;i=13",
                "__REALTIME_TIMESTAMP": "1700000001000000",
                "_SYSTEMD_UNIT": "robovac-matterbridge.service",
                "PRIORITY": "6",
                "MESSAGE": "Bridge gestartet",
            }),
            stderr="",
        )

        result = system_services.get_system_service_logs(
            cursor="s=abc;i=12"
        )
        command = run.call_args.args[0]

        self.assertTrue(result["success"])
        self.assertEqual(result["cursor"], "s=next;i=13")
        self.assertEqual(
            result["entries"][0]["service"],
            "Matterbridge",
        )
        self.assertIn(
            "robovac-matterbridge.service",
            command,
        )
        self.assertIn(
            "s=abc;i=12",
            command,
        )

    @patch(
        "monolith.system_services.os.path.isdir",
        return_value=False,
    )
    def test_logs_are_disabled_without_systemd(
        self,
        _isdir,
    ):
        result = system_services.get_system_service_logs()

        self.assertTrue(result["success"])
        self.assertFalse(result["supported"])
        self.assertEqual(result["entries"], [])


if __name__ == "__main__":
    unittest.main()
