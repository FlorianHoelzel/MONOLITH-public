import tempfile
import unittest
from pathlib import Path

from monolith import database


class CameraEventDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        database.DATABASE_PATH = (
            Path(self.directory.name)
            / "monolith.db"
        )
        database.init_database()

    def tearDown(self):
        database.DATABASE_PATH = (
            self.original_database_path
        )
        self.directory.cleanup()

    def test_filters_motion_events_by_source_and_time(self):
        database.save_event(
            event_type="motion",
            source_id="motion_livingroom",
            room="Wohnzimmer",
            title="Bewegung erkannt",
            created_at=1100,
        )
        database.save_event(
            event_type="motion",
            source_id="motion_livingroom",
            room="Wohnzimmer",
            title="Bewegung erkannt",
            created_at=1150,
        )
        database.save_event(
            event_type="motion",
            source_id="motion_kitchen",
            room="Küche",
            title="Bewegung erkannt",
            created_at=1200,
        )
        database.save_event(
            event_type="device",
            source_id="motion_livingroom",
            room="Wohnzimmer",
            title="Gerät geschaltet",
            created_at=1300,
        )
        database.save_event(
            event_type="motion",
            source_id="motion_livingroom",
            room="Wohnzimmer",
            title="Alte Bewegung",
            created_at=900,
        )

        events = database.get_events_since(
            event_type="motion",
            since_timestamp=1000,
            source_id="motion_livingroom",
        )

        self.assertEqual(
            [event["timestamp"] for event in events],
            [1150, 1100],
        )
        self.assertTrue(
            all(
                event["source_id"]
                == "motion_livingroom"
                for event in events
            )
        )
if __name__ == "__main__":
    unittest.main()
