# app/core/push.py
"""
Web Push sender.

Sends home-screen push notifications to users' phones/browsers via the
Web Push protocol (no Firebase, no SNS — the browser vendors' push
services deliver them).

Required Lambda environment variables:
  VAPID_PUBLIC_KEY    - from `npx web-push generate-vapid-keys`
  VAPID_PRIVATE_KEY   - same command (keep secret)
  VAPID_CLAIM_EMAIL   - contact email, e.g. admin@skyrina.com.mx

Requires: pip install pywebpush
(NOTE: pywebpush depends on `cryptography`, a compiled library — build
the Lambda package on Linux, e.g. with `sam build`, Docker, or
`pip install --platform manylinux2014_x86_64 --only-binary=:all:`.)
"""

import json
import os

from pywebpush import webpush, WebPushException
from sqlalchemy.orm import Session

from app.models.push_subscription_model import PushSubscription

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_CLAIM_EMAIL = os.getenv("VAPID_CLAIM_EMAIL", "admin@example.com")


def send_push(db: Session, user_id, title: str, body: str, url: str = "/"):
    """
    Send a push notification to every device the user has subscribed.

    Never raises: push delivery is best-effort and must never break the
    business operation (ticket creation/completion) that triggered it.
    Expired subscriptions (HTTP 404/410) are cleaned up automatically.
    """
    if not VAPID_PRIVATE_KEY:
        print("send_push skipped: VAPID_PRIVATE_KEY not configured")
        return 0

    subs = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user_id)
        .all()
    )

    if not subs:
        return 0

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
    })

    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth,
                    },
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{VAPID_CLAIM_EMAIL}"},
            )
            sent += 1
        except WebPushException as e:
            status = e.response.status_code if e.response is not None else None
            if status in (404, 410):
                # Subscription expired or user revoked permission — drop it
                db.delete(sub)
            else:
                print(f"Push failed for {sub.endpoint[:60]}...: {e}")
        except Exception as e:
            print(f"Push error: {e}")

    try:
        db.commit()  # persist any deleted expired subscriptions
    except Exception:
        db.rollback()

    return sent