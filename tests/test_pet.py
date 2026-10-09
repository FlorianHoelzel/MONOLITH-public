import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from monolith import app as app_module
from monolith import database
from monolith import pet_monitor
from monolith.push_notifications import PushDeliveryRejected


class PetDatabaseTests(unittest.TestCase):
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

    def test_pet_entries_can_be_created_and_completed(self):
        feeding_id = database.create_pet_feeding_time(
            "Frühstück",
            "08:00",
        )
        weight_id = database.create_pet_weight(
            5000,
            "2026-09-26",
        )
        shopping_id = database.create_pet_shopping_item(
            "Nassfutter"
        )

        database.set_pet_feeding_completed(
            feeding_id,
            "2026-09-26",
            True,
        )
        database.set_pet_shopping_item_checked(
            shopping_id,
            True,
        )
        result = database.get_pet_data("2026-09-26")

        self.assertTrue(result["feeding_times"][0]["completed"])
        self.assertEqual(result["weights"][0]["weight_grams"], 5000)
        self.assertTrue(result["shopping_items"][0]["checked"])

        self.assertTrue(database.delete_pet_feeding_time(feeding_id))
        self.assertTrue(database.delete_pet_weight(weight_id))
        self.assertTrue(
            database.delete_pet_shopping_item(shopping_id)
        )

    def test_missing_acknowledgement_does_not_replay_accepted_feeding(self):
        feeding_id = database.create_pet_feeding_time(
            "Abendessen",
            "18:00",
        )

        due = database.get_due_pet_feedings(
            "2026-09-26",
            "18:01",
        )
        self.assertEqual([item["id"] for item in due], [feeding_id])

        database.mark_pet_feeding_notified(
            feeding_id,
            "2026-09-26",
        )
        self.assertEqual(
            database.get_due_pet_feedings(
                "2026-09-26",
                "20:00",
            ),
            [],
        )

        self.assertTrue(
            database.acknowledge_pet_feeding_notification(
                feeding_id,
                "2026-09-26",
            )
        )
        self.assertEqual(
            database.get_due_pet_feedings(
                "2026-09-26",
                "20:00",
            ),
            [],
        )


class PetApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        database.DATABASE_PATH = (
            Path(self.temporary_directory.name) / "monolith.db"
        )
        database.init_database()
        self.client = app_module.app.test_client()

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def test_full_pet_api_lifecycle(self):
        feeding_response = self.client.post(
            "/api/pet/feedings",
            json={
                "label": "Frühstück",
                "time_of_day": "08:15",
            },
        )
        self.assertEqual(feeding_response.status_code, 201)
        feeding_id = feeding_response.get_json()["entry_id"]

        completion_response = self.client.put(
            f"/api/pet/feedings/{feeding_id}/completion",
            json={"completed": True},
        )
        self.assertEqual(completion_response.status_code, 200)

        self.assertEqual(
            self.client.post(
                "/api/pet/weights",
                json={
                    "weight_kg": "5,00",
                    "recorded_on": "2026-09-26",
                },
            ).status_code,
            201,
        )
        self.assertEqual(
            self.client.post(
                "/api/pet/shopping",
                json={"name": "Leckerlis"},
            ).status_code,
            201,
        )

        data = self.client.get("/api/pet").get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["feeding_times"][0]["completed"])
        self.assertEqual(data["weights"][0]["weight_grams"], 5000)
        self.assertEqual(data["shopping_items"][0]["name"], "Leckerlis")

    def test_invalid_values_are_rejected(self):
        self.assertEqual(
            self.client.post(
                "/api/pet/feedings",
                json={"label": "", "time_of_day": "25:00"},
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/pet/weights",
                json={"weight_kg": "0", "recorded_on": "kaputt"},
            ).status_code,
            400,
        )


class PetReminderTests(unittest.TestCase):
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

    @patch("monolith.pet_monitor.send_push_notification")
    def test_due_reminder_is_sent_and_deduplicated(self, send_mock):
        database.create_pet_feeding_time("Abendessen", "18:00")
        database.save_push_subscription(
            "https://push.example.test/device",
            "key",
            "auth",
        )
        now = datetime(2026, 9, 26, 18, 1)

        self.assertEqual(
            pet_monitor.send_due_pet_reminders(now),
            1,
        )
        self.assertEqual(
            pet_monitor.send_due_pet_reminders(now),
            0,
        )
        send_mock.assert_called_once()

    def add_feeding_and_subscriptions(self, endpoints):
        feeding_id = database.create_pet_feeding_time("Mittagessen", "12:00")
        for endpoint in endpoints:
            database.save_push_subscription(endpoint, "key", "auth")
        return feeding_id

    @patch("monolith.pet_monitor.send_push_notification")
    def test_no_replay_without_lan_ack_even_after_restart(self, send_mock):
        self.add_feeding_and_subscriptions(["https://push.test/phone"])
        now = datetime(2026, 10, 4, 12, 0)
        pet_monitor.send_due_pet_reminders(now)
        database.init_database()  # simulate restart with persistent state
        for minutes in (1, 2, 5, 60):
            pet_monitor.send_due_pet_reminders(now + timedelta(minutes=minutes))
        send_mock.assert_called_once()

    @patch("monolith.pet_monitor.send_push_notification")
    def test_rejected_second_device_retries_without_repeating_first(self, send_mock):
        self.add_feeding_and_subscriptions(["https://push.test/one", "https://push.test/two"])
        send_mock.side_effect = [None, PushDeliveryRejected(503), None]
        now = datetime(2026, 10, 4, 12, 0)
        pet_monitor.send_due_pet_reminders(now)
        pet_monitor.send_due_pet_reminders(now + timedelta(seconds=5))
        self.assertEqual(send_mock.call_count, 2)
        pet_monitor.send_due_pet_reminders(now + timedelta(seconds=61))
        self.assertEqual(send_mock.call_count, 3)
        endpoints = [call.args[0]["endpoint"] for call in send_mock.call_args_list]
        self.assertEqual(endpoints, ["https://push.test/one", "https://push.test/two", "https://push.test/two"])

    @patch("monolith.pet_monitor.send_push_notification", side_effect=TimeoutError)
    def test_timeout_with_unknown_provider_acceptance_is_not_replayed(self, send_mock):
        self.add_feeding_and_subscriptions(["https://push.test/phone"])
        now = datetime(2026, 10, 4, 12, 0)
        pet_monitor.send_due_pet_reminders(now)
        pet_monitor.send_due_pet_reminders(now + timedelta(minutes=2))
        send_mock.assert_called_once()

    @patch("monolith.pet_monitor.send_push_notification")
    def test_accepted_http_followed_by_db_failure_does_not_duplicate(self, send_mock):
        self.add_feeding_and_subscriptions(["https://push.test/phone"])
        now = datetime(2026, 10, 4, 12, 0)
        with patch("monolith.pet_monitor.finish_pet_push_delivery", side_effect=RuntimeError("DB locked")):
            with self.assertRaises(RuntimeError):
                pet_monitor.send_due_pet_reminders(now)
        pet_monitor.send_due_pet_reminders(now + timedelta(minutes=2))
        send_mock.assert_called_once()

    def test_claim_is_atomic_and_survives_restart(self):
        feeding_id = self.add_feeding_and_subscriptions(["https://push.test/phone"])
        args = (feeding_id, "2026-10-04", "https://push.test/phone", 100)
        self.assertEqual(database.claim_pet_push_delivery(*args), 1)
        self.assertIsNone(database.claim_pet_push_delivery(*args))
        database.init_database()
        self.assertIsNone(database.claim_pet_push_delivery(*args))

    @patch("monolith.pet_monitor.send_push_notification")
    def test_migration_does_not_replay_legacy_unacknowledged_send(self, send_mock):
        feeding_id = self.add_feeding_and_subscriptions(["https://push.test/phone"])
        database.mark_pet_feeding_notified(feeding_id, "2026-10-04")
        connection = database.get_connection()
        connection.execute("DROP TABLE pet_push_deliveries")
        connection.commit()
        connection.close()
        database.init_database()
        pet_monitor.send_due_pet_reminders(datetime(2026, 10, 4, 12, 1))
        send_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
