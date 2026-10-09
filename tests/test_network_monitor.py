import tempfile
import unittest
from pathlib import Path

from monolith import database
from monolith import network_monitor


class NetworkDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        database.DATABASE_PATH = Path(self.temporary_directory.name) / "monolith.db"
        database.init_database()

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def test_network_device_memory_keeps_user_flags(self):
        database.remember_network_device(
            "02:00:00:00:00:09",
            "Notebook",
            True,
            known_on_create=False,
        )
        database.update_network_device_flags(
            "02:00:00:00:00:09",
            is_known=True,
            is_important=True,
        )
        database.remember_network_device(
            "02:00:00:00:00:09",
            "Notebook neu",
            False,
        )

        device = database.get_network_devices_memory()["02:00:00:00:00:09"]
        self.assertEqual(device["name"], "Notebook neu")
        self.assertEqual(device["is_known"], 1)
        self.assertEqual(device["is_important"], 1)
        self.assertEqual(device["was_active"], 0)
        self.assertIsNotNone(device["last_online"])

    def test_network_event_deduplication_is_feed_local(self):
        first = database.save_network_event(
            "internet_lost",
            "Internetverbindung verloren",
            dedupe_key="internet:0",
            dedupe_seconds=60,
            created_at=1000,
        )
        second = database.save_network_event(
            "internet_lost",
            "Internetverbindung verloren",
            dedupe_key="internet:0",
            dedupe_seconds=60,
            created_at=1030,
        )

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(database.get_network_events()), 1)


class NetworkNormalizationTests(unittest.TestCase):
    def test_mesh_topology_becomes_stable_hierarchy(self):
        topology = {
            "nodes": [
                {
                    "uid": "router",
                    "device_name": "FRITZ!Box",
                    "device_model": "FRITZ!Box 7590",
                    "device_role": "MESH_MASTER",
                    "device_mac_address": "02:00:00:00:00:0A",
                    "node_interfaces": [{
                        "uid": "router-wlan",
                        "type": "WLAN",
                        "node_links": [{
                            "node_1_uid": "router",
                            "node_2_uid": "phone",
                            "type": "WLAN",
                            "state": "CONNECTED",
                        }],
                    }],
                },
                {
                    "uid": "phone",
                    "device_name": "Telefon",
                    "device_model": "Smartphone",
                    "device_mac_address": "02:00:00:00:00:0B",
                    "node_interfaces": [],
                },
            ],
        }

        result = network_monitor._normalize_mesh(topology)

        self.assertEqual(result["node_count"], 2)
        self.assertEqual(result["roots"][0]["name"], "FRITZ!Box")
        self.assertEqual(result["roots"][0]["children"][0]["name"], "Telefon")
        self.assertEqual(
            result["access_points"]["02:00:00:00:00:0B"],
            "FRITZ!Box",
        )

    def test_wlan_service_uses_reported_six_ghz_band(self):
        result = network_monitor._normalize_wlan_network(
            3,
            {
                "NewEnable": True,
                "NewSSID": "Zuhause",
                "NewOperatingFrequencyBand": "6GHz",
                "NewChannel": 37,
            },
            [],
        )

        self.assertEqual(result["band"], "6 GHz")
        self.assertFalse(result["guest"])
        self.assertEqual(result["channel"], 37)


if __name__ == "__main__":
    unittest.main()
