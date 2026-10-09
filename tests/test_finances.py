import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path


TEST_DATA_DIRECTORY = tempfile.TemporaryDirectory()
os.environ["MONOLITH_DATA_DIR"] = TEST_DATA_DIRECTORY.name


from monolith import database


class FinanceDatabaseTests(unittest.TestCase):
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

    def test_monthly_summary_combines_all_entry_types(self):
        database.create_finance_recurring(
            "income",
            "Beispieleinnahme",
            300000,
            "2026-09",
        )
        database.create_finance_recurring(
            "fixed_expense",
            "Beispielfixkosten",
            90000,
            "2026-09",
        )
        database.create_finance_expense(
            "Beispielausgabe",
            6500,
            "2026-09-12",
        )
        database.create_finance_expense(
            "Anderer Monat",
            9900,
            "2026-10-01",
        )

        result = database.get_finances("2026-09")

        self.assertEqual(result["summary"]["income_cents"], 300000)
        self.assertEqual(result["summary"]["fixed_expense_cents"], 90000)
        self.assertEqual(result["summary"]["variable_expense_cents"], 6500)
        self.assertEqual(result["summary"]["carried_over_cents"], 0)
        self.assertEqual(result["summary"]["available_cents"], 203500)
        self.assertEqual(len(result["expenses"]), 1)

    def test_remaining_balance_is_carried_into_next_month(self):
        database.create_finance_recurring(
            "income",
            "Beispieleinnahme",
            300000,
            "2026-08",
        )
        database.create_finance_recurring(
            "fixed_expense",
            "Beispielfixkosten",
            100000,
            "2026-08",
        )
        database.create_finance_expense(
            "August-Ausgabe",
            50000,
            "2026-08-20",
        )
        database.create_finance_expense(
            "September-Ausgabe",
            20000,
            "2026-09-10",
        )

        august = database.get_finances("2026-08")
        september = database.get_finances("2026-09")

        self.assertEqual(august["summary"]["available_cents"], 150000)
        self.assertEqual(
            september["summary"]["carried_over_cents"],
            150000,
        )
        self.assertEqual(
            september["summary"]["available_cents"],
            330000,
        )

    def test_manual_transfer_applies_once_and_carries_forward(self):
        database.set_finance_transfer("2026-09", 125000)
        database.create_finance_expense(
            "September-Ausgabe",
            25000,
            "2026-09-10",
        )

        september = database.get_finances("2026-09")
        october = database.get_finances("2026-10")

        self.assertEqual(
            september["summary"]["manual_transfer_cents"],
            125000,
        )
        self.assertEqual(
            september["summary"]["carried_over_cents"],
            125000,
        )
        self.assertEqual(
            september["summary"]["available_cents"],
            100000,
        )
        self.assertEqual(
            october["summary"]["carried_over_cents"],
            100000,
        )

    def test_manual_transfer_can_be_updated_and_removed(self):
        database.set_finance_transfer("2026-09", 50000)
        database.set_finance_transfer("2026-09", 75000)

        result = database.get_finances("2026-09")
        self.assertEqual(
            result["summary"]["manual_transfer_cents"],
            75000,
        )

        database.set_finance_transfer("2026-09", 0)
        result = database.get_finances("2026-09")
        self.assertEqual(
            result["summary"]["manual_transfer_cents"],
            0,
        )
        self.assertEqual(result["summary"]["available_cents"], 0)

    def test_entries_can_be_deleted(self):
        recurring_id = database.create_finance_recurring(
            "income",
            "Nebenjob",
            25000,
            "2026-09",
        )
        expense_id = database.create_finance_expense(
            "Einkauf",
            4200,
            "2026-09-18",
        )

        self.assertTrue(
            database.delete_finance_recurring(recurring_id)
        )
        self.assertTrue(
            database.delete_finance_expense(expense_id)
        )
        self.assertFalse(
            database.delete_finance_expense(expense_id)
        )

        result = database.get_finances("2026-09")
        self.assertEqual(result["recurring"], [])
        self.assertEqual(result["expenses"], [])

    def test_recurring_entry_can_end_without_changing_previous_months(self):
        recurring_id = database.create_finance_recurring(
            "fixed_expense",
            "Alter Vertrag",
            10000,
            "2026-08",
        )

        self.assertTrue(
            database.delete_finance_recurring(
                recurring_id,
                "2026-10",
            )
        )

        august = database.get_finances("2026-08")
        september = database.get_finances("2026-09")
        october = database.get_finances("2026-10")

        self.assertEqual(len(august["recurring"]), 1)
        self.assertEqual(august["summary"]["fixed_expense_cents"], 10000)
        self.assertEqual(len(september["recurring"]), 1)
        self.assertEqual(september["summary"]["fixed_expense_cents"], 10000)
        self.assertEqual(october["recurring"], [])
        self.assertEqual(october["summary"]["fixed_expense_cents"], 0)
        self.assertEqual(october["summary"]["carried_over_cents"], -20000)

    def test_recurring_entry_created_and_removed_same_month_is_deleted(self):
        recurring_id = database.create_finance_recurring(
            "income",
            "Kurzfristig",
            5000,
            "2026-10",
        )

        self.assertTrue(
            database.delete_finance_recurring(
                recurring_id,
                "2026-10",
            )
        )
        self.assertEqual(database.get_finances("2026-10")["recurring"], [])

    def test_existing_recurring_entries_receive_a_start_month(self):
        database.DATABASE_PATH.unlink()
        connection = sqlite3.connect(database.DATABASE_PATH)
        connection.execute(
            """
            CREATE TABLE finance_recurring (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_type TEXT NOT NULL,
                name TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO finance_recurring (
                entry_type,
                name,
                amount_cents,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "income",
                "Bestehender Eintrag",
                10000,
                int(time.mktime((2026, 8, 15, 12, 0, 0, 0, 0, -1))),
            ),
        )
        connection.commit()
        connection.close()

        database.init_database()

        connection = database.get_connection()
        row = connection.execute(
            "SELECT start_month FROM finance_recurring"
        ).fetchone()
        columns = {
            column["name"]
            for column in connection.execute(
                "PRAGMA table_info(finance_recurring)"
            )
        }
        connection.close()
        self.assertEqual(row["start_month"], "2026-08")
        self.assertIn("end_month", columns)


if __name__ == "__main__":
    unittest.main()
