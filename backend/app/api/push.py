"""Web Push (PWA) endpoints: configuration, subscribe and unsubscribe."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.push import (
    push_enabled,
    remove_subscription,
    save_subscription,
    vapid_public_key,
)

router = APIRouter(prefix="/push", tags=["push"])


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=16)
    auth: str = Field(min_length=8)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10)
    keys: SubscriptionKeys


@router.get("/config")
def push_config(_user: User = Depends(get_current_user)):
    return {
        "enabled": push_enabled(),
        "public_key": vapid_public_key() if push_enabled() else None,
        "supported": True,
    }


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
def subscribe(
    data: SubscriptionIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not push_enabled():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Web push is not enabled.")
    save_subscription(
        db,
        user,
        endpoint=data.endpoint,
        p256dh=data.keys.p256dh,
        auth=data.keys.auth,
        user_agent=request.headers.get("user-agent"),
    )
    return {"endpoint": data.endpoint, "enabled": True}


@router.delete("/subscribe")
def unsubscribe(
    data: SubscriptionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    removed = remove_subscription(db, user, data.endpoint)
    return {"removed": removed}