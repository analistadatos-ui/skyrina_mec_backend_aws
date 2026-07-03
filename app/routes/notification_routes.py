# app/routes/notification_routes.py
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.push_subscription_model import PushSubscription

router = APIRouter(
    prefix="/notificaciones",
    tags=["Notificaciones"],
)


# ==========================================
# GET VAPID PUBLIC KEY
# The frontend needs this to subscribe.
# ==========================================
@router.get("/vapid-public-key")
def get_vapid_public_key():
    key = os.getenv("VAPID_PUBLIC_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="VAPID_PUBLIC_KEY no configurada")
    return {"success": True, "public_key": key}


# ==========================================
# SUBSCRIBE
# Body: { user_id, subscription: { endpoint, keys: { p256dh, auth } } }
# (the `subscription` object is exactly what the browser returns
#  from pushManager.subscribe(), serialized with .toJSON())
# ==========================================
class SubscribeRequest(BaseModel):
    user_id: str
    subscription: dict


@router.post("/subscribe")
def subscribe(payload: SubscribeRequest, db: Session = Depends(get_db)):
    try:
        user_uuid = uuid.UUID(payload.user_id)

        endpoint = payload.subscription.get("endpoint")
        keys = payload.subscription.get("keys") or {}
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")

        if not endpoint or not p256dh or not auth:
            raise HTTPException(status_code=400, detail="Suscripción inválida")

        # Upsert by endpoint: re-subscribing the same device just
        # refreshes ownership (e.g. shared device, different login).
        existing = (
            db.query(PushSubscription)
            .filter(PushSubscription.endpoint == endpoint)
            .first()
        )

        if existing:
            existing.user_id = user_uuid
            existing.p256dh = p256dh
            existing.auth = auth
        else:
            db.add(PushSubscription(
                user_id=user_uuid,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
            ))

        db.commit()
        return {"success": True, "message": "Notificaciones activadas"}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"Error subscribing to push: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# UNSUBSCRIBE
# Body: { endpoint }
# ==========================================
class UnsubscribeRequest(BaseModel):
    endpoint: str


@router.post("/unsubscribe")
def unsubscribe(payload: UnsubscribeRequest, db: Session = Depends(get_db)):
    try:
        (
            db.query(PushSubscription)
            .filter(PushSubscription.endpoint == payload.endpoint)
            .delete()
        )
        db.commit()
        return {"success": True, "message": "Notificaciones desactivadas"}
    except Exception as e:
        db.rollback()
        print(f"Error unsubscribing: {e}")
        raise HTTPException(status_code=500, detail=str(e))