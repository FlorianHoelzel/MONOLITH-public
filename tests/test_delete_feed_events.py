import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "delete-feed-events.py"
)
SPEC = importlib.util.spec_from_file_location(
    "delete_feed_events",
    SCRIPT_PATH,
)
delete_feed_events = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(delete_feed_events)


class DeleteFeedEventsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "monolith.db"
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY,
                source_id TEXT,
                title TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO events (id, source_id, title) VALUES (?, ?, ?)",
            [
                (1257, "presence_person_2", "Away"),
                (1258, "presence_person_2", "Home"),
                (1300, "another_source", "Keep"),
            ],
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.directory.cleanup()

    def test_deletes_only_verified_events_and_creates_backup(self):
        rows, backup_path = delete_feed_events.delete_events(
            self.database_path,
            [1257, 1258],
            "presence_person_2",
        )

        self.assertEqual([row[0] for row in rows], [1257, 1258])
        self.assertTrue(backup_path.exists())

        connection = sqlite3.connect(self.database_path)
        remaining = connection.execute(
            "SELECT id FROM events ORDER BY id"
        ).fetchall()
        connection.close()
        self.assertEqual(remaining, [(1300,)])

        backup = sqlite3.connect(backup_path)
        original = backup.execute(
            "SELECT id FROM events ORDER BY id"
        ).fetchall()
        backup.close()
        self.assertEqual(original, [(1257,), (1258,), (1300,)])

    def test_aborts_if_an_event_has_the_wrong_source(self):
        with self.assertRaises(RuntimeError):
            delete_feed_events.delete_events(
                self.database_path,
                [1257, 1300],
                "presence_person_2",
            )


if __name__ == "__main__":
    unittest.main()
