import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from pywebpush import WebPushException
from types import SimpleNamespace
from pywebpush import WebPushException

from monolith import database
from monolith import push_notifications
from monolith import app as app_module


class PushSubscriptionDatabaseTests(unittest.TestCase):
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

    def test_subscription_can_be_saved_updated_and_deleted(self):
        endpoint = "https://push.example.test/device"
        database.save_push_subscription(
            endpoint,
            "first-key",
            "first-auth",
            "Test Browser",
        )
        database.save_push_subscription(
            endpoint,
            "updated-key",
            "updated-auth",
            "Test Browser",
        )

        self.assertEqual(
            database.get_push_subscription(endpoint),
            {
                "endpoint": endpoint,
                "keys": {
                    "p256dh": "updated-key",
                    "auth": "updated-auth",
                },
            },
        )
        self.assertTrue(
            database.delete_push_subscription(endpoint)
        )
        self.assertIsNone(
            database.get_push_subscription(endpoint)
        )

    def test_subscription_rotation_replaces_old_endpoint_without_replaying_meal(self):
        old_endpoint = "https://push.test/old"
        new_endpoint = "https://push.test/new"
        database.save_push_subscription(old_endpoint, "key", "auth")
        feeding_id = database.create_pet_feeding_time("Mittagessen", "12:00")
        database.claim_pet_push_delivery(feeding_id, "2026-10-04", old_endpoint, 100)
        database.finish_pet_push_delivery(feeding_id, "2026-10-04", old_endpoint, "accepted", 101)
        database.save_push_subscription(new_endpoint, "new-key", "new-auth", previous_endpoint=old_endpoint)
        self.assertIsNone(database.get_push_subscription(old_endpoint))
        self.assertEqual(len(database.get_push_subscriptions()), 1)
        self.assertIsNone(database.claim_pet_push_delivery(feeding_id, "2026-10-04", new_endpoint, 200))

    def test_subscription_rotation_replaces_old_endpoint_without_replaying_meal(self):
        old_endpoint = "https://push.test/old"
        new_endpoint = "https://push.test/new"
        database.save_push_subscription(old_endpoint, "key", "auth")
        feeding_id = database.create_pet_feeding_time("Mittagessen", "12:00")
        database.claim_pet_push_delivery(feeding_id, "2026-10-04", old_endpoint, 100)
        database.finish_pet_push_delivery(feeding_id, "2026-10-04", old_endpoint, "accepted", 101)
        database.save_push_subscription(new_endpoint, "new-key", "new-auth", previous_endpoint=old_endpoint)
        self.assertIsNone(database.get_push_subscription(old_endpoint))
        self.assertEqual(len(database.get_push_subscriptions()), 1)
        self.assertIsNone(database.claim_pet_push_delivery(feeding_id, "2026-10-04", new_endpoint, 200))


class VapidKeyTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_key_path = (
            push_notifications.VAPID_PRIVATE_KEY_PATH
        )
        push_notifications.VAPID_PRIVATE_KEY_PATH = (
            Path(self.temporary_directory.name) / "vapid.pem"
        )

    def tearDown(self):
        push_notifications.VAPID_PRIVATE_KEY_PATH = (
            self.original_key_path
        )
        self.temporary_directory.cleanup()

    def test_public_key_is_stable_and_web_push_encoded(self):
        first_key = push_notifications.get_vapid_public_key()
        second_key = push_notifications.get_vapid_public_key()
        padding = "=" * (-len(first_key) % 4)
        decoded = base64.urlsafe_b64decode(
            first_key + padding
        )

        self.assertEqual(first_key, second_key)
        self.assertEqual(len(decoded), 65)
        self.assertEqual(decoded[0], 4)
        self.assertTrue(
            push_notifications.VAPID_PRIVATE_KEY_PATH.exists()
        )

    def test_default_vapid_subject_is_an_https_url(self):
        self.assertEqual(
            push_notifications.VAPID_SUBJECT,
            "https://example.com",
        )

    @patch("monolith.push_notifications.webpush")
    def test_notification_uses_generated_private_key(
        self,
        webpush_mock,
    ):
        subscription = {
            "endpoint": "https://push.example.test/device",
            "keys": {
                "p256dh": "key",
                "auth": "auth",
            },
        }

        push_notifications.send_push_notification(
            subscription,
            "MONOLITH",
            "Test",
            tag="test-notification",
        )

        webpush_mock.assert_called_once()
        arguments = webpush_mock.call_args.kwargs
        self.assertEqual(
            arguments["subscription_info"],
            subscription,
        )
        self.assertEqual(
            arguments["vapid_private_key"],
            str(push_notifications.VAPID_PRIVATE_KEY_PATH),
        )
        self.assertEqual(
            arguments["headers"]["Urgency"],
            "high",
        )
        topic = arguments["headers"]["Topic"]
        self.assertLessEqual(len(topic), 32)
        self.assertRegex(topic, r"^[A-Za-z0-9_-]+$")
        self.assertEqual(arguments["ttl"], 21600)
        payload = json.loads(arguments["data"])
        self.assertEqual(payload["web_push"], 8030)
        self.assertEqual(payload["notification"]["navigate"], "https://monolith.local/")
        self.assertEqual(payload["notification"]["title"], payload["title"])
        self.assertEqual(payload["notification"]["tag"], payload["tag"])

    @patch("monolith.push_notifications.webpush")
    def test_provider_rejection_preserves_status_and_retry_after(self, webpush_mock):
        webpush_mock.side_effect = WebPushException(
            "rejected", response=SimpleNamespace(status_code=429, headers={"Retry-After": "120"})
        )
        with self.assertRaises(push_notifications.PushDeliveryRejected) as caught:
            push_notifications.send_push_notification({}, "Test", "Test")
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(caught.exception.retry_after, 120)

    @patch("monolith.push_notifications.webpush")
    def test_invalid_subscription_is_removed_instead_of_retried(self, webpush_mock):
        webpush_mock.side_effect = WebPushException(
            "gone", response=SimpleNamespace(status_code=410, headers={})
        )
        with self.assertRaises(push_notifications.PushSubscriptionGone):
            push_notifications.send_push_notification({}, "Test", "Test")

    @patch("monolith.push_notifications.webpush")
    def test_provider_rejection_preserves_status_and_retry_after(self, webpush_mock):
        webpush_mock.side_effect = WebPushException(
            "rejected", response=SimpleNamespace(status_code=429, headers={"Retry-After": "120"})
        )
        with self.assertRaises(push_notifications.PushDeliveryRejected) as caught:
            push_notifications.send_push_notification({}, "Test", "Test")
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(caught.exception.retry_after, 120)

    @patch("monolith.push_notifications.webpush")
    def test_invalid_subscription_is_removed_instead_of_retried(self, webpush_mock):
        webpush_mock.side_effect = WebPushException(
            "gone", response=SimpleNamespace(status_code=410, headers={})
        )
        with self.assertRaises(push_notifications.PushSubscriptionGone):
            push_notifications.send_push_notification({}, "Test", "Test")


class PushApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        self.original_key_path = (
            push_notifications.VAPID_PRIVATE_KEY_PATH
        )
        database.DATABASE_PATH = (
            Path(self.temporary_directory.name) / "monolith.db"
        )
        push_notifications.VAPID_PRIVATE_KEY_PATH = (
            Path(self.temporary_directory.name) / "vapid.pem"
        )
        database.init_database()
        self.client = app_module.app.test_client()

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        push_notifications.VAPID_PRIVATE_KEY_PATH = (
            self.original_key_path
        )
        self.temporary_directory.cleanup()

    def test_public_key_and_subscription_lifecycle(self):
        key_response = self.client.get(
            "/api/push/public-key"
        )
        self.assertEqual(key_response.status_code, 200)
        self.assertTrue(
            key_response.get_json()["public_key"]
        )

        subscription = {
            "endpoint": "https://push.example.test/device",
            "keys": {
                "p256dh": "device-key",
                "auth": "device-auth",
            },
        }
        subscribe_response = self.client.post(
            "/api/push/subscribe",
            json=subscription,
        )
        self.assertEqual(subscribe_response.status_code, 200)
        self.assertIsNotNone(
            database.get_push_subscription(
                subscription["endpoint"]
            )
        )

        status_response = self.client.post(
            "/api/push/status",
            json={
                "endpoint": subscription["endpoint"],
            },
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(
            status_response.get_json()["subscribed"]
        )

        unsubscribe_response = self.client.post(
            "/api/push/unsubscribe",
            json={
                "endpoint": subscription["endpoint"],
            },
        )
        self.assertEqual(unsubscribe_response.status_code, 200)
        self.assertIsNone(
            database.get_push_subscription(
                subscription["endpoint"]
            )
        )

        status_response = self.client.post(
            "/api/push/status",
            json={
                "endpoint": subscription["endpoint"],
            },
        )
        self.assertFalse(
            status_response.get_json()["subscribed"]
        )

    @patch("monolith.app.send_push_notification")
    def test_test_notification_uses_saved_subscription(
        self,
        send_mock,
    ):
        endpoint = "https://push.example.test/device"
        database.save_push_subscription(
            endpoint,
            "device-key",
            "device-auth",
        )

        response = self.client.post(
            "/api/push/test",
            json={
                "endpoint": endpoint,
            },
        )

        self.assertEqual(response.status_code, 200)
        send_mock.assert_called_once()

    def test_notification_acknowledges_pet_delivery(self):
        feeding_id = database.create_pet_feeding_time(
            "Mittagessen",
            "12:00",
        )
        database.mark_pet_feeding_notified(
            feeding_id,
            "2026-09-28",
        )

        response = self.client.post(
            "/api/push/ack",
            json={
                "message_id": (
                    f"pet:2026-09-28:{feeding_id}"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(
            database.get_due_pet_feedings(
                "2026-09-28",
                "13:00",
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
