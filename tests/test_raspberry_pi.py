import subprocess
import unittest
from unittest.mock import patch

from monolith import raspberry_pi


class RaspberryPiStatusTest(unittest.TestCase):
    def test_parse_key_values_keeps_values_with_separator(self):
        result = raspberry_pi._parse_key_values(
            "NAME=Raspberry Pi OS\nURL=https://example.test?a=b",
            separator="=",
        )

        self.assertEqual(result["NAME"], "Raspberry Pi OS")
        self.assertEqual(result["URL"], "https://example.test?a=b")

    @patch("monolith.raspberry_pi._read_cpu_times")
    @patch("monolith.raspberry_pi.time.sleep")
    def test_cpu_usage_uses_busy_delta(self, _sleep, read_times):
        read_times.side_effect = [
            (1000, 700),
            (1100, 720),
        ]

        self.assertEqual(raspberry_pi._read_cpu_usage(), 80.0)

    @patch("monolith.raspberry_pi._read_text")
    def test_memory_uses_mem_available(self, read_text):
        read_text.return_value = (
            "MemTotal:       1000000 kB\n"
            "MemAvailable:    250000 kB\n"
            "SwapTotal:       100000 kB\n"
            "SwapFree:         75000 kB\n"
        )

        memory, swap = raspberry_pi._read_memory()

        self.assertEqual(memory["usage_percent"], 75.0)
        self.assertEqual(swap["usage_percent"], 25.0)

    @patch("monolith.raspberry_pi.subprocess.run")
    def test_throttling_decodes_current_and_historic_flags(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="throttled=0x50005\n",
            stderr="",
        )

        result = raspberry_pi._read_throttling()

        self.assertTrue(result["active"])
        self.assertTrue(result["occurred"])
        self.assertIn("Unterspannung erkannt", result["issues"])
        self.assertIn("Drosselung seit dem Start", result["issues"])

    def test_health_checks_flag_hot_and_full_system(self):
        checks = raspberry_pi._health_checks(
            82.5,
            {"usage_percent": 96.2},
            {"active": False, "occurred": False, "issues": []},
            False,
        )

        states = {
            check["id"]: check["state"]
            for check in checks
        }
        self.assertEqual(states["temperature"], "critical")
        self.assertEqual(states["storage"], "critical")
        self.assertEqual(states["throttling"], "healthy")
        self.assertEqual(states["reboot"], "healthy")


if __name__ == "__main__":
    unittest.main()
