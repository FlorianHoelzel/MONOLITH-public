import threading
from datetime import datetime

from monolith.database import (
    delete_push_subscription,
    claim_pet_push_delivery,
    finish_pet_push_delivery,
    get_due_pet_feedings,
    get_push_subscriptions,
    mark_pet_feeding_notified,
)
from monolith.push_notifications import (
    PushSubscriptionGone,
    PushDeliveryRejected,
    PUSH_TTL_SECONDS,
    send_push_notification,
)


PET_REMINDER_INTERVAL_SECONDS = 5

_monitor_started = False
_delivery_lock = threading.Lock()


def send_due_pet_reminders(now=None):
    with _delivery_lock:
        return _send_due_pet_reminders(now)


def _send_due_pet_reminders(now=None):
    current = now or datetime.now()
    notification_date = current.date().isoformat()
    current_time = current.strftime("%H:%M")
    subscriptions = get_push_subscriptions()

    if not subscriptions:
        return 0

    sent_reminders = 0

    for feeding in get_due_pet_feedings(
        notification_date,
        current_time,
        include_notified=True,
    ):
        delivered = False
        delivery_count = 0

        for subscription in subscriptions:
            due_at = datetime.fromisoformat(
                f"{notification_date}T{feeding['time_of_day']}"
            )
            ttl = PUSH_TTL_SECONDS - int((current - due_at).total_seconds())
            if ttl <= 0:
                continue
            timestamp = int(current.timestamp())
            attempt = claim_pet_push_delivery(
                feeding["id"], notification_date,
                subscription["endpoint"], timestamp,
            )
            if attempt is None:
                continue
            status = "unknown"
            retry_after = 0
            try:
                message_id = (
                    f"pet:{notification_date}:"
                    f"{feeding['id']}"
                )
                send_push_notification(
                    subscription,
                    "Futterzeit für dein Haustier",
                    f"{feeding['label']} ist jetzt dran.",
                    url="/?tab=pet",
                    tag=(
                        f"pet-feeding-{feeding['id']}-"
                        f"{notification_date}"
                    ),
                    message_id=message_id,
                    ttl=ttl,
                )
                status = "accepted"
                delivered = True
                delivery_count += 1
            except PushSubscriptionGone:
                status = "gone"
                delete_push_subscription(
                    subscription["endpoint"]
                )
            except PushDeliveryRejected as error:
                status = "retry" if error.retryable else "rejected"
                retry_after = max(error.retry_after, min(900, 60 * 2 ** (attempt - 1)))
                print(f"[PET] Push abgewiesen: HTTP {error.status_code}, Versuch {attempt}")
            except Exception as error:
                # A timeout can occur AFTER the provider accepted the push.
                # Repeating an ambiguous request creates visible duplicates.
                print(
                    "[PET] Push-Ergebnis unklar, keine automatische Doppelzustellung: "
                    f"{type(error).__name__}"
                )
            finish_pet_push_delivery(
                feeding["id"], notification_date,
                subscription["endpoint"], status, timestamp, retry_after,
            )

        if delivered:
            mark_pet_feeding_notified(
                feeding["id"],
                notification_date,
            )
            print(
                "[PET] Push-Anbieter hat Erinnerung angenommen: "
                f"{feeding['label']} "
                f"({delivery_count} Endgerät(e))"
            )
            sent_reminders += 1

    return sent_reminders


def start_pet_monitor():
    global _monitor_started

    if _monitor_started:
        return

    _monitor_started = True

    def monitor_loop():
        while True:
            try:
                send_due_pet_reminders()
            except Exception as error:
                print(
                    "[PET] Erinnerungsprüfung fehlgeschlagen: "
                    f"{error}"
                )

            threading.Event().wait(
                PET_REMINDER_INTERVAL_SECONDS
            )

    thread = threading.Thread(
        target=monitor_loop,
        name="monolith-pet-monitor",
        daemon=True,
    )
    thread.start()
