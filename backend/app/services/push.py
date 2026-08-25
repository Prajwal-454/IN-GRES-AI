"""Web Push (PWA) notification delivery.

Provides VAPID key management (generated once and persisted under the data
directory unless configured explicitly) and a thin wrapper over ``pywebpush``
that sends a browser push notification for a registered subscription.

Push is opt-in: nothing is sent until a user subscribes a browser and
``WEB_PUSH_ENABLED`` is on. Delivery failures are logged and never raise.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.push import PushSubscription
from app.models.user import User

logger = logging.getLogger(__name__)

_VAPID_KEY_FILE = "vapid-keys.json"
_keys: tuple[str, str] | None = None  # (public_key, private_key)


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _load_or_create_keys() -> tuple[str, str]:
    """Return (public_key, private_key) base64url VAPID keys.

    Uses explicit settings when provided, otherwise reads/creates the key file
    under the data directory so keys stay stable across restarts.
    """
    global _keys
    if _keys is not None:
        return _keys

    settings = get_settings()
    if settings.WEB_PUSH_VAPID_PUBLIC_KEY and settings.WEB_PUSH_VAPID_PRIVATE_KEY:
        _keys = (settings.WEB_PUSH_VAPID_PUBLIC_KEY, settings.WEB_PUSH_VAPID_PRIVATE_KEY)
        return _keys

    data_dir = settings.data_dir
    key_path = data_dir / _VAPID_KEY_FILE
    if key_path.is_file():
        try:
            lines = key_path.read_text(encoding="utf-8").strip().splitlines()
            if len(lines) == 2 and lines[0] and lines[1]:
                _keys = (lines[0].strip(), lines[1].strip())
                return _keys
        except OSError as exc:
            logger.warning("could not read VAPID key file: %s", exc)

    private_key: EllipticCurvePrivateKey = ec.generate_private_key(ec.SECP256R1())
    public_numbers = private_key.public_key().public_numbers()
    raw_public = (
        b"\x04"
        + public_numbers.x.to_bytes(32, "big")
        + public_numbers.y.to_bytes(32, "big")
    )
    raw_private = private_key.private_numbers().private_value.to_bytes(32, "big")
    _keys = (_urlsafe_b64encode(raw_public), _urlsafe_b64encode(raw_private))

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        key_path.write_text(f"{_keys[0]}\n{_keys[1]}\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("could not persist VAPID keys (%s); keys are ephemeral", exc)
    return _keys


def vapid_public_key() -> str:
    return _load_or_create_keys()[0]


def push_enabled() -> bool:
    return get_settings().WEB_PUSH_ENABLED


def send_push(
    subscription: PushSubscription,
    title: str,
    body: str | None,
    url: str | None = None,
) -> bool:
    """Deliver a push notification to one subscription. Returns success."""
    if not push_enabled():
        return False
    try:
        from pywebpush import WebPushException, webpush

        public_key, private_key = _load_or_create_keys()
        payload = {"title": title, "body": body or "", "url": url or "/notifications"}
        settings = get_settings()
        response = webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload).encode("utf-8"),
            vapid_private_key=private_key,
            vapid_claims={"sub": f"mailto:{settings.WEB_PUSH_EMAIL}"},
            timeout=10,
        )
        if response is not None:
            logger.debug("push delivered: %s", response.status_code)
        return True
    except WebPushException as exc:
        # 404/410 means the subscription is gone and should be removed.
        if getattr(exc, "response", None) is not None and exc.response.status_code in (404, 410):
            logger.info("push subscription no longer valid, will be dropped: %s", exc.message)
            return False
        logger.warning("push delivery failed: %s", exc)
        return False
    except Exception as exc:  # noqa: BLE001 - push must never break the request
        logger.warning("push delivery failed: %s", exc)
        return False


def send_push_to_user(
    db: Session, user_id: int, title: str, body: str | None, url: str | None = None
) -> int:
    """Send a push to every subscription registered by a user.

    Returns the number of successful deliveries; expired subscriptions are
    removed from the database.
    """
    if not push_enabled():
        return 0
    subs = list(db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all())
    delivered = 0
    for sub in subs:
        if send_push(sub, title, body, url):
            delivered += 1
        else:
            db.delete(sub)
    if subs:
        db.commit()
    return delivered


def save_subscription(
    db: Session,
    user: User,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str | None = None,
) -> PushSubscription:
    """Create or refresh a browser push subscription for a user."""
    sub = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
    if sub is None:
        sub = PushSubscription(user_id=user.id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        db.add(sub)
    else:
        sub.user_id = user.id
        sub.p256dh = p256dh
        sub.auth = auth
    sub.user_agent = user_agent
    db.commit()
    db.refresh(sub)
    return sub


def remove_subscription(db: Session, user: User, endpoint: str) -> bool:
    sub = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id)
        .first()
    )
    if sub is None:
        return False
    db.delete(sub)
    db.commit()
    return True
