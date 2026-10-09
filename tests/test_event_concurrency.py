import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from monolith import database


class EventConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(
            database, "DATABASE_PATH", Path(self.directory.name) / "monolith.db"
        )
        self.path_patch.start()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.path_patch.stop)
        database.init_database()

    def test_feed_reads_committed_events_during_an_exclusive_write(self):
        first_id = database.save_event("motion", "First", source_id="sensor", room="Room", created_at=100)
        second_id = database.save_event("motion", "Second", source_id="sensor", room="Room", created_at=100)
        writer = database.get_connection()
        try:
            writer.execute("BEGIN EXCLUSIVE")
            writer.execute("UPDATE events SET title = 'Uncommitted'")
            # With the old rollback journal this SELECT raises 'database is locked'.
            events = database.get_recent_events(limit=1)
            self.assertEqual(events[0]["id"], second_id)
            self.assertEqual(events[0]["title"], "Second")
            older = database.get_recent_events(before_timestamp=100, before_id=second_id)
            self.assertEqual([event["id"] for event in older], [first_id])
            self.assertEqual(older[0]["title"], "First")
        finally:
            writer.rollback()
            writer.close()

    def test_connections_wait_for_writers_and_keep_wal_after_reinitializing(self):
        database.init_database()
        connection = database.get_connection()
        try:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], 30000)
        finally:
            connection.close()

    def test_failed_feed_query_closes_its_connection(self):
        connection = Mock()
        connection.cursor.return_value.execute.side_effect = sqlite3.OperationalError("database is locked")
        with patch.object(database, "get_connection", return_value=connection):
            with self.assertRaises(sqlite3.OperationalError):
                database.get_recent_events()
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
