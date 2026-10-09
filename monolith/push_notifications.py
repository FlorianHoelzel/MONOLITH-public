import base64
import hashlib
import json
import os
import threading
from urllib.parse import urljoin, urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush

from monolith.data_paths import data_path


VAPID_PRIVATE_KEY_PATH = data_path("vapid_private_key.pem")
VAPID_SUBJECT = os.getenv(
    "MONOLITH_VAPID_SUBJECT",
    "https://example.com",
)

_key_lock = threading.Lock()
PUSH_PUBLIC_ORIGIN = "https://monolith.local"
PUSH_TTL_SECONDS = 6 * 60 * 60


class PushSubscriptionGone(Exception):
    pass


class PushDeliveryRejected(Exception):
    def __init__(self, status_code, retry_after=60):
        super().__init__(f"Push-Anbieter hat HTTP {status_code} zurückgegeben")
        self.status_code = status_code
        self.retryable = status_code == 429 or status_code >= 500
        self.retry_after = retry_after


def _ensure_private_key():
    with _key_lock:
        if VAPID_PRIVATE_KEY_PATH.exists():
            return

        VAPID_PRIVATE_KEY_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        private_key = ec.generate_private_key(
            ec.SECP256R1()
        )
        key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        temporary_path = VAPID_PRIVATE_KEY_PATH.with_suffix(
            ".tmp"
        )
        temporary_path.write_bytes(key_bytes)

        try:
            os.chmod(temporary_path, 0o600)
        except OSError:
            pass

        temporary_path.replace(VAPID_PRIVATE_KEY_PATH)


def get_vapid_public_key():
    _ensure_private_key()
    private_key = serialization.load_pem_private_key(
        VAPID_PRIVATE_KEY_PATH.read_bytes(),
        password=None,
    )
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(
        public_key
    ).rstrip(b"=").decode("ascii")


def send_push_notification(
    subscription,
    title,
    body,
    url="/",
    tag=None,
    message_id=None,
    ttl=PUSH_TTL_SECONDS,
):
    _ensure_private_key()
    topic_source = message_id or tag or "monolith"
    topic = base64.urlsafe_b64encode(
        hashlib.sha256(
            topic_source.encode("utf-8")
        ).digest()
    ).rstrip(b"=").decode("ascii")[:32]
    navigate = urljoin(PUSH_PUBLIC_ORIGIN + "/", url)
    if (
        urlparse(navigate).scheme != "https"
        or urlparse(navigate).netloc != urlparse(PUSH_PUBLIC_ORIGIN).netloc
    ):
        navigate = PUSH_PUBLIC_ORIGIN + "/"
    payload = {
        # iOS 18.4+ can display this even when the service worker is absent
        # or fails. Keep legacy fields for already installed workers.
        "web_push": 8030,
        "notification": {
            "title": title,
            "body": body,
            "navigate": navigate,
            "tag": tag or "monolith",
            "silent": False,
        },
        "title": title,
        "body": body,
        "url": url,
        "tag": tag or "monolith",
        "message_id": message_id,
    }

    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=str(
                VAPID_PRIVATE_KEY_PATH
            ),
            vapid_claims={
                "sub": VAPID_SUBJECT,
            },
            ttl=ttl,
            timeout=15,
            headers={
                "Urgency": "high",
                "Topic": topic,
            },
        )
    except WebPushException as error:
        status_code = getattr(
            error.response,
            "status_code",
            None,
        )

        if status_code in {404, 410}:
            raise PushSubscriptionGone() from error

        if status_code is not None:
            try:
                retry_after = max(60, int(error.response.headers.get("Retry-After", 60)))
            except (TypeError, ValueError):
                retry_after = 60
            raise PushDeliveryRejected(status_code, retry_after) from error

        raise
