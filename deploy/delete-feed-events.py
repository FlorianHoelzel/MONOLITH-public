import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


DEFAULT_DATABASE = Path("/var/lib/monolith/monolith.db")


def delete_events(database_path, event_ids, expected_source):
    database_path = Path(database_path)
    placeholders = ", ".join("?" for _ in event_ids)
    connection = sqlite3.connect(database_path)

    try:
        rows = connection.execute(
            f"""
            SELECT id, source_id, title
            FROM events
            WHERE id IN ({placeholders})
            ORDER BY id
            """,
            event_ids,
        ).fetchall()

        if not rows:
            return [], None

        unexpected = [
            row for row in rows
            if row[1] != expected_source
        ]
        if unexpected:
            raise RuntimeError(
                "Abbruch: Mindestens eine ID gehört nicht zu "
                f"{expected_source}."
            )

        found_ids = {row[0] for row in rows}
        missing_ids = sorted(set(event_ids) - found_ids)
        if missing_ids:
            raise RuntimeError(
                "Abbruch: Ereignis-IDs nicht gefunden: "
                + ", ".join(str(event_id) for event_id in missing_ids)
            )

        backup_path = database_path.with_name(
            database_path.name
            + ".backup-before-event-cleanup-"
            + datetime.now().strftime("%Y%m%d-%H%M%S")
        )
        backup = sqlite3.connect(backup_path)
        try:
            connection.backup(backup)
        finally:
            backup.close()

        connection.execute(
            f"""
            DELETE FROM events
            WHERE id IN ({placeholders})
              AND source_id = ?
            """,
            [*event_ids, expected_source],
        )
        connection.commit()
        return rows, backup_path
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Löscht gezielt Feed-Ereignisse und erstellt vorher "
            "ein SQLite-Backup."
        )
    )
    parser.add_argument("event_ids", nargs="+", type=int)
    parser.add_argument(
        "--source",
        required=True,
        help="Erwartete source_id als Sicherheitsprüfung",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
    )
    args = parser.parse_args()

    rows, backup_path = delete_events(
        args.database,
        args.event_ids,
        args.source,
    )

    if not rows:
        print("Keine passenden Ereignisse gefunden; nichts geändert.")
        return

    print(f"Backup: {backup_path}")
    for event_id, source_id, title in rows:
        print(f"Gelöscht: {event_id} · {source_id} · {title}")


if __name__ == "__main__":
    main()
