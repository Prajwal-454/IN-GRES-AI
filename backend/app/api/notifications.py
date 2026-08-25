"""Notifications and alert-rule endpoints for the signed-in user."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.notification import AlertRule, UserNotification
from app.models.user import User
from app.services.alerts import check_all_alerts

router = APIRouter(prefix="/notifications", tags=["notifications"])


class RuleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    metric: str = Field(pattern="^(stage|recharge|extraction|resource)$")
    operator: str = Field(pattern="^(gt|gte|lt|lte)$")
    threshold: float
    state: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    village: str | None = Field(default=None, max_length=120)
    year: int | None = Field(default=None, ge=1900, le=2100)
    channels: list[str] = Field(default_factory=lambda: ["in_app"])
    cooldown_minutes: int = Field(default=1440, ge=0)
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    metric: str | None = Field(default=None, pattern="^(stage|recharge|extraction|resource)$")
    operator: str | None = Field(default=None, pattern="^(gt|gte|lt|lte)$")
    threshold: float | None = None
    state: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    village: str | None = Field(default=None, max_length=120)
    year: int | None = Field(default=None, ge=1900, le=2100)
    channels: list[str] | None = None
    cooldown_minutes: int | None = Field(default=None, ge=0)
    enabled: bool | None = None


def _rule_out(rule: AlertRule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "metric": rule.metric,
        "operator": rule.operator,
        "threshold": rule.threshold,
        "state": rule.state,
        "district": rule.district,
        "village": rule.village,
        "year": rule.year,
        "channels": rule.channels or ["in_app"],
        "cooldown_minutes": rule.cooldown_minutes,
        "enabled": rule.enabled,
        "last_triggered_at": rule.last_triggered_at,
        "created_at": rule.created_at,
    }


def _notification_out(n: UserNotification) -> dict:
    return {
        "id": n.id,
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "payload": n.payload,
        "read": n.read,
        "created_at": n.created_at,
    }


@router.get("")
def list_notifications(
    limit: int = Query(default=50, le=200),
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(UserNotification).where(UserNotification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(UserNotification.read.is_(False))
    stmt = stmt.order_by(UserNotification.created_at.desc(), UserNotification.id.desc()).limit(limit)
    rows = list(db.scalars(stmt))
    unread = int(
        db.scalar(
            select(func.count())
            .select_from(UserNotification)
            .where(UserNotification.user_id == user.id, UserNotification.read.is_(False))
        )
        or 0
    )
    return {"notifications": [_notification_out(n) for n in rows], "unread": unread}


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    note = db.scalar(
        select(UserNotification).where(
            UserNotification.id == notification_id,
            UserNotification.user_id == user.id,
        )
    )
    if not note:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    note.read = True
    db.commit()
    return {"id": note.id, "read": True}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = list(
        db.scalars(
            select(UserNotification).where(
                UserNotification.user_id == user.id,
                UserNotification.read.is_(False),
            )
        )
    )
    for note in rows:
        note.read = True
    db.commit()
    return {"marked": len(rows)}


@router.get("/rules")
def list_rules(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rules = list(db.scalars(select(AlertRule).where(AlertRule.user_id == user.id).order_by(AlertRule.id)))
    return [_rule_out(r) for r in rules]


@router.post("/rules", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_rule(data: RuleCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rule = AlertRule(
        user_id=user.id,
        name=data.name,
        metric=data.metric,
        operator=data.operator,
        threshold=data.threshold,
        state=data.state,
        district=data.district,
        village=data.village,
        year=data.year,
        channels=data.channels or ["in_app"],
        cooldown_minutes=data.cooldown_minutes,
        enabled=data.enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_out(rule)


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: int,
    data: RuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rule = db.scalar(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user.id)
    )
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    for field_name, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field_name, value)
    db.commit()
    db.refresh(rule)
    return _rule_out(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rule = db.scalar(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user.id)
    )
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    db.delete(rule)
    db.commit()
    return None


@router.post("/check")
def run_alert_check(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Manually evaluate the current user's enabled rules."""
    created = check_all_alerts(db, user_id=user.id)
    return {"created": created}