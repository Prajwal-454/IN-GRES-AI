"""Alert rules engine and notification delivery.

Evaluates each user's enabled AlertRule against the groundwater assessment
data, creates in-app UserNotification rows when conditions are met, and
optionally sends email through SMTP. Rules have a per-rule cooldown so users
are not spammed with the same alert on every import.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.groundwater import (
    AssessmentUnit,
    District,
    GroundwaterAssessment,
    State,
    Village,
)
from app.models.notification import AlertRule, UserNotification

logger = logging.getLogger(__name__)

_METRIC_COLUMNS = {
    "stage": GroundwaterAssessment.stage_of_extraction,
    "recharge": GroundwaterAssessment.recharge_total,
    "extraction": GroundwaterAssessment.extraction_total,
    "resource": GroundwaterAssessment.annual_extractable_resource,
}

_OPERATORS = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
}

_METRIC_LABELS = {
    "stage": "Stage of extraction",
    "recharge": "Recharge",
    "extraction": "Extraction",
    "resource": "Extractable resource",
}


def _within_cooldown(rule: AlertRule, now: datetime) -> bool:
    if rule.last_triggered_at is None:
        return False
    cutoff = rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes or 0)
    return cutoff > now


def _evaluate_rule(db: Session, rule: AlertRule, now: datetime, dataset_ids: set[int] | None = None) -> int:
    """Create notifications for units matching the rule. Returns count created."""
    column = _METRIC_COLUMNS.get(rule.metric)
    operator = _OPERATORS.get(rule.operator)
    if column is None or operator is None:
        logger.warning("alert rule %s has unsupported metric/operator", rule.id)
        return 0

    stmt = (
        select(
            GroundwaterAssessment,
            State.name,
            District.name,
            Village.name,
            AssessmentUnit.name,
        )
        .join(AssessmentUnit, GroundwaterAssessment.assessment_unit_id == AssessmentUnit.id)
        .join(District, AssessmentUnit.district_id == District.id)
        .join(State, AssessmentUnit.state_id == State.id)
        .outerjoin(Village, AssessmentUnit.village_id == Village.id)
        .where(column.is_not(None))
    )
    if rule.year is not None:
        stmt = stmt.where(GroundwaterAssessment.assessment_year == rule.year)
    else:
        # Most recent year that has a value for this metric, per unit.
        sub = (
            select(
                GroundwaterAssessment.assessment_unit_id.label("unit_id"),
                func.max(GroundwaterAssessment.assessment_year).label("y"),
            )
            .where(column.is_not(None))
            .group_by(GroundwaterAssessment.assessment_unit_id)
            .subquery()
        )
        stmt = stmt.join(sub, sub.c.unit_id == GroundwaterAssessment.assessment_unit_id)
        stmt = stmt.where(GroundwaterAssessment.assessment_year == sub.c.y)

    if rule.state:
        stmt = stmt.where(func.lower(State.name) == rule.state.strip().lower())
    if rule.district:
        stmt = stmt.where(func.lower(District.name) == rule.district.strip().lower())
    if getattr(rule, "village", None):
        stmt = stmt.where(func.lower(Village.name) == rule.village.strip().lower())
    if dataset_ids:
        stmt = stmt.where(GroundwaterAssessment.dataset_id.in_(dataset_ids))

    rows = db.execute(stmt).all()
    matches = [r for r in rows if operator(getattr(r[0], column.key), rule.threshold)]

    if not matches:
        return 0

    for assessment, state, district, village, unit in matches:
        value = getattr(assessment, column.key)
        title = f"{_METRIC_LABELS[rule.metric]} alert: {unit}"
        scope = f"{unit}, {district}, {state}"
        if village:
            scope = f"{unit} ({village}), {district}, {state}"
        body = (
            f"{scope} ({assessment.assessment_year}) has "
            f"{_METRIC_LABELS[rule.metric].lower()} = {value} which "
            f"{'exceeds' if rule.operator in ('gt', 'gte') else 'falls below'} the "
            f"threshold {rule.threshold}."
        )
        _deliver(
            db,
            user_id=rule.user_id,
            rule_id=rule.id,
            kind="alert",
            title=title,
            body=body,
            payload={
                "metric": rule.metric,
                "operator": rule.operator,
                "threshold": rule.threshold,
                "value": float(value),
                "state": state,
                "district": district,
                "village": village,
                "unit": unit,
                "year": assessment.assessment_year,
            },
        )

    rule.last_triggered_at = now
    db.commit()
    return len(matches)


def _deliver(db: Session, user_id: int, rule_id: int | None, kind: str, title: str, body: str | None, payload: dict | None) -> None:
    db.add(
        UserNotification(
            user_id=user_id,
            rule_id=rule_id,
            kind=kind,
            title=title,
            body=body,
            payload=payload,
            read=False,
        )
    )
    settings = get_settings()
    if settings.EMAIL_NOTIFICATIONS_ENABLED and settings.SMTP_HOST:
        from app.models.user import User

        user = db.get(User, user_id)
        if user:
            _send_email(user.email, f"[IN-GRES AI] {title}", body or "")

    # Web Push (PWA): fire-and-forget to any registered browser subscriptions.
    if settings.WEB_PUSH_ENABLED:
        from app.services.push import send_push_to_user

        send_push_to_user(db, user_id, title, body, url="/notifications")


def _send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
    except Exception as exc:  # noqa: BLE001 - email delivery must never break the request
        logger.warning("email delivery failed to %s: %s", to, exc)


def check_all_alerts(db: Session, user_id: int | None = None) -> int:
    """Evaluate every enabled rule. Returns number of notifications created."""
    if not get_settings().NOTIFICATIONS_ENABLED:
        return 0
    now = datetime.now(timezone.utc)
    stmt = select(AlertRule).where(AlertRule.enabled.is_(True))
    if user_id is not None:
        stmt = stmt.where(AlertRule.user_id == user_id)
    rules = list(db.scalars(stmt))
    created = 0
    for rule in rules:
        if _within_cooldown(rule, now):
            continue
        created += _evaluate_rule(db, rule, now)
    return created


def check_alerts_for_import(db: Session, dataset_id: int) -> int:
    """Evaluate enabled rules limited to a freshly imported dataset."""
    if not get_settings().NOTIFICATIONS_ENABLED:
        return 0
    now = datetime.now(timezone.utc)
    rules = list(db.scalars(select(AlertRule).where(AlertRule.enabled.is_(True))))
    created = 0
    for rule in rules:
        if _within_cooldown(rule, now):
            continue
        created += _evaluate_rule(db, rule, now, dataset_ids={dataset_id})
    return created