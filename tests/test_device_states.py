import tempfile
import unittest
from pathlib import Path

from monolith import database


class DeviceStateDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        database.DATABASE_PATH = (
            Path(self.temporary_directory.name) / "monolith.db"
        )
        database.init_database()

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def test_device_state_survives_a_new_database_connection(self):
        database.save_device_state(
            "device_light_07",
            True,
        )

        self.assertEqual(
            database.get_device_states(),
            {"device_light_07": True},
        )

    def test_empty_sensor_history_restores_as_empty_mapping(self):
        self.assertEqual(
            database.get_latest_sensor_values(),
            {},
        )

    def test_saving_device_state_updates_existing_value(self):
        database.save_device_state(
            "device_light_04",
            True,
        )
        database.save_device_state(
            "device_light_04",
            False,
        )

        self.assertEqual(
            database.get_device_states(),
            {"device_light_04": False},
        )


if __name__ == "__main__":
    unittest.main()
