"""Admin endpoints: user management, audit logs, dataset overview and the
command-centre overview (groundwater, AI/RAG, queries, health)."""

from __future__ import annotations

import platform
import sys
import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.audit import write_audit
from app.core.security import hash_password
from app.database import get_db
from app.models.audit import AuditLog
from app.models.conversation import Conversation, Message
from app.models.groundwater import (
    AssessmentUnit,
    Dataset,
    GroundwaterLevel,
    GroundwaterRainfall,
)
from app.models.notification import AlertRule, UserNotification
from app.models.rag import KnowledgeChunk, KnowledgeDocument
from app.models.user import User
from app.config import get_settings

router = APIRouter(prefix="/admin", tags=["admin"])

_admin = Depends(require_roles("admin"))


class UserAdminOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    language_pref: str
    is_active: bool
    last_login_at: object | None = None
    created_at: object | None = None


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(user|expert|admin)$")
    is_active: bool | None = None


class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str = Field(min_length=8)
    role: str = Field(default="user", pattern="^(user|expert|admin)$")


@router.get("/users", response_model=list[UserAdminOut])
def list_users(
    db: Session = Depends(get_db),
    _admin_user: User = _admin,
):
    return list(db.scalars(select(User).order_by(User.id)))


@router.post("/users", response_model=UserAdminOut, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    admin_user: User = _admin,
):
    existing = db.scalar(select(User).where(User.email == data.email.lower()))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_audit(db, admin_user, "ADMIN_USER_CREATE", "user", user.id, {"email": user.email})
    return user


@router.patch("/users/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    admin_user: User = _admin,
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin_user.id and data.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")

    changes: dict = {}
    if data.role is not None and data.role != user.role:
        if user.id == admin_user.id and data.role != "admin":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot demote your own account")
        user.role = data.role
        changes["role"] = data.role
    if data.is_active is not None and data.is_active != user.is_active:
        user.is_active = data.is_active
        changes["is_active"] = data.is_active

    db.commit()
    db.refresh(user)
    if changes:
        write_audit(db, admin_user, "ADMIN_USER_UPDATE", "user", user.id, changes)
    return user


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _admin_user: User = _admin,
):
    rows = list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)))
    out = []
    for r in rows:
        user = db.get(User, r.user_id) if r.user_id else None
        out.append(
            {
                "id": r.id,
                "action": r.action,
                "resource": r.resource,
                "resource_id": r.resource_id,
                "user": user.full_name if user else None,
                "details": r.details,
                "created_at": r.created_at,
            }
        )
    return out


@router.get("/datasets")
def list_datasets(
    db: Session = Depends(get_db),
    _admin_user: User = _admin,
):
    rows = list(db.scalars(select(Dataset).order_by(Dataset.id)))
    return [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "source": d.source,
            "publication_year": d.publication_year,
            "version": d.version,
            "geographic_level": d.geographic_level,
            "validation_status": d.validation_status,
            "is_demo": d.is_demo,
        }
        for d in rows
    ]


# ---------------------------------------------------------------------------
# Command centre: overview, query monitor, model metrics
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = (
    (100.0, "critical", "Critical"),
    (90.0, "critical", "Critical"),
)


def _severity_for_stage(stage: float | None) -> dict:
    if stage is None:
        return {"level": "unknown", "label": "Unknown"}
    if stage > 100:
        return {"level": "critical", "label": "Over-exploited"}
    if stage >= 90:
        return {"level": "critical", "label": "Critical"}
    if stage >= 70:
        return {"level": "warning", "label": "Semi-critical"}
    return {"level": "ok", "label": "Safe"}


@router.get("/overview")
def admin_overview(
    db: Session = Depends(get_db),
    _admin_user: User = _admin,
):
    """One aggregate payload powering the admin command centre."""
    from app.api import analytics
    from app.ingres import queries

    settings = get_settings()

    # --- Groundwater -----------------------------------------------------
    summary = queries.get_summary(db)
    latest_year = queries.get_latest_year(db)
    category_counts = {
        c["category"]: c["count"] for c in summary["category_counts"]
    }
    ranking_rows = analytics.district_ranking_data(db, None, latest_year, "stage")
    critical_zones = []
    for r in ranking_rows[:8]:
        stage = r.get("stage_of_extraction")
        sev = _severity_for_stage(stage)
        critical_zones.append(
            {
                "district": r.get("district"),
                "state": r.get("state"),
                "stage": stage,
                "category": sev["label"],
                "severity": sev["level"],
            }
        )

    units = db.scalar(select(func.count(AssessmentUnit.id))) or 0
    level_rows = db.scalar(select(func.count(GroundwaterLevel.id))) or 0
    rainfall_rows = db.scalar(select(func.count(GroundwaterRainfall.id))) or 0

    # --- Alerts ----------------------------------------------------------
    enabled_rules = (
        db.scalar(select(func.count(AlertRule.id)).where(AlertRule.enabled.is_(True)))
        or 0
    )
    week_ago = time.time() - 7 * 86400
    recent_alerts = 0
    try:
        from datetime import datetime, timezone

        cutoff = datetime.fromtimestamp(week_ago, tz=timezone.utc)
        recent_alerts = (
            db.scalar(
                select(func.count(UserNotification.id)).where(
                    UserNotification.created_at >= cutoff
                )
            )
            or 0
        )
    except Exception:  # pragma: no cover - timezone quirks on sqlite
        recent_alerts = int(
            db.scalar(select(func.count(UserNotification.id))) or 0
        )

    # --- AI / RAG --------------------------------------------------------
    docs = db.scalar(select(func.count(KnowledgeDocument.id))) or 0
    chunks = db.scalar(select(func.count(KnowledgeChunk.id))) or 0

    # --- Queries / conversations ----------------------------------------
    total_conversations = db.scalar(select(func.count(Conversation.id))) or 0
    total_messages = db.scalar(select(func.count(Message.id))) or 0
    assistant_msgs = (
        db.scalar(
            select(func.count(Message.id)).where(Message.role == "assistant")
        )
        or 0
    )
    intent_rows = db.execute(
        select(Message.intent, func.count(Message.id))
        .where(Message.role == "assistant")
        .group_by(Message.intent)
    ).all()
    intent_counts = {intent or "unknown": n for intent, n in intent_rows}
    helpful = (
        db.scalar(select(func.count(Message.id)).where(Message.rating == 1)) or 0
    )
    not_helpful = (
        db.scalar(select(func.count(Message.id)).where(Message.rating == -1)) or 0
    )
    recent_chats = list(
        db.scalars(
            select(Message)
            .where(Message.role == "assistant")
            .order_by(Message.id.desc())
            .limit(25)
        )
    )

    # --- Users -----------------------------------------------------------
    users_total = db.scalar(select(func.count(User.id))) or 0
    role_rows = db.execute(select(User.role, func.count(User.id)).group_by(User.role)).all()
    users_by_role = {role: n for role, n in role_rows}
    active_users = (
        db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    )

    # --- System health ---------------------------------------------------
    db_ok = bool(db.execute(select(1)).first())
    datasets_total = db.scalar(select(func.count(Dataset.id))) or 0

    return {
        "groundwater": {
            "latest_year": latest_year,
            "assessment_units": summary["assessment_units"],
            "total_units_registered": units,
            "recharge_hm3": round(summary["total_recharge"], 1),
            "extraction_hm3": round(summary["total_extraction"], 1),
            "avg_stage_pct": round(summary["average_stage_of_extraction"], 1),
            "category_counts": category_counts,
            "monitoring_levels": level_rows,
            "rainfall_records": rainfall_rows,
            "critical_zones": critical_zones,
        },
        "alerts": {
            "enabled_rules": enabled_rules,
            "triggered_last_7d": recent_alerts,
        },
        "datasets": {
            "total": datasets_total,
        },
        "ai": {
            "llm_enabled": settings.LLM_ENABLED,
            "llm_provider": settings.LLM_PROVIDER,
            "llm_model": settings.resolved_llm_model(),
            "search_model": settings.resolved_llm_search_model() or None,
            "web_search_enabled": settings.WEB_SEARCH_ENABLED,
            "rag_documents": docs,
            "rag_chunks": chunks,
        },
        "queries": {
            "conversations": total_conversations,
            "messages": total_messages,
            "assistant_answers": assistant_msgs,
            "intent_counts": intent_counts,
            "feedback_helpful": helpful,
            "feedback_not_helpful": not_helpful,
        },
        "users": {
            "total": users_total,
            "active": active_users,
            "by_role": users_by_role,
        },
        "system": {
            "database_ok": db_ok,
            "python_version": sys.version.split()[0],
            "platform": platform.system(),
            "environment": settings.ENVIRONMENT,
        },
    }


@router.get("/queries")
def admin_query_monitor(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    _admin_user: User = _admin,
):
    """Recent assistant answers with intent, language and feedback status."""
    rows = list(
        db.scalars(
            select(Message)
            .where(Message.role == "assistant")
            .order_by(Message.id.desc())
            .limit(limit)
        )
    )
    out = []
    for m in rows:
        conv = db.get(Conversation, m.conversation_id)
        user = db.get(User, conv.user_id) if conv else None
        # The question is the closest preceding user message.
        question = None
        if conv:
            prior = db.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conv.id,
                    Message.role == "user",
                    Message.id < m.id,
                )
                .order_by(Message.id.desc())
                .limit(1)
            ).first()
            question = prior.content if prior else None
        out.append(
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "user": user.email if user else None,
                "question": question,
                "answer_preview": (m.content or "")[:160],
                "intent": m.intent,
                "response_type": m.response_type,
                "language": m.language,
                "is_demo": m.is_demo,
                "rating": m.rating,
                "created_at": m.created_at,
            }
        )
    return out


@router.get("/models/metrics")
def admin_model_metrics(
    state: str = Query(default="Telangana"),
    metric: str = Query(default="stage", pattern="^(stage|recharge|extraction)$"),
    db: Session = Depends(get_db),
    _admin_user: User = _admin,
):
    """Per-model validation metrics (cached) for the Models control tab."""
    from app.ingres import predict, query_cache

    cache_key = ("admin_model_metrics", state, metric)
    cached = query_cache.cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        bt = predict.backtest(db, state=state, metric=metric)
    except Exception as exc:  # pragma: no cover - tiny dev datasets etc.
        return {"state": state, "metric": metric, "models": [], "error": str(exc)}
    models_out = []
    for name, stats in (bt.get("evaluation") or {}).items():
        models_out.append(
            {
                "model": name,
                "rmse": stats.get("rmse"),
                "mae": stats.get("mae"),
                "mape": stats.get("mape"),
                "direction_accuracy": stats.get("direction_accuracy"),
            }
        )
    models_out.sort(key=lambda m: (m["rmse"] is None, m["rmse"]))
    payload = {
        "state": state,
        "metric": metric,
        "best_model": bt.get("best") or (models_out[0]["model"] if models_out else None),
        "models": models_out,
        "generated_at": time.time(),
    }
    query_cache.cache_set(cache_key, payload)
    return payload
