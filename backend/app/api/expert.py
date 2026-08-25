"""Expert assistance: request escalation and resolution workflows."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.audit import write_audit
from app.database import get_db
from app.models.expert import ExpertRequest
from app.models.user import User

router = APIRouter(prefix="/expert", tags=["expert"])


class ExpertRequestCreate(BaseModel):
    question: str = Field(min_length=3)
    conversation_id: int | None = None
    language: str | None = None
    location: str | None = None
    intent: str | None = None


class ExpertRequestUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(NEW|IN_PROGRESS|RESOLVED|CLOSED)$")
    priority: str | None = Field(default=None, pattern="^(LOW|MEDIUM|HIGH|URGENT)$")
    resolution: str | None = None


class ExpertRequestOut(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    conversation_id: int | None
    question: str
    language: str | None
    location: str | None
    intent: str | None
    status: str
    priority: str | None
    resolution: str | None
    assigned_expert_id: int | None
    assigned_expert_name: str | None = None
    resolved_at: datetime | None
    created_at: datetime


def _to_out(db: Session, req: ExpertRequest) -> ExpertRequestOut:
    user = db.get(User, req.user_id)
    expert = db.get(User, req.assigned_expert_id) if req.assigned_expert_id else None
    return ExpertRequestOut(
        id=req.id,
        user_id=req.user_id,
        user_name=user.full_name if user else None,
        conversation_id=req.conversation_id,
        question=req.question,
        language=req.language,
        location=req.location,
        intent=req.intent,
        status=req.status,
        priority=req.priority,
        resolution=req.resolution,
        assigned_expert_id=req.assigned_expert_id,
        assigned_expert_name=expert.full_name if expert else None,
        resolved_at=req.resolved_at,
        created_at=req.created_at,
    )


@router.post("/requests", response_model=ExpertRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    data: ExpertRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = ExpertRequest(
        user_id=user.id,
        conversation_id=data.conversation_id,
        question=data.question,
        language=data.language,
        location=data.location,
        intent=data.intent,
        status="NEW",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    write_audit(db, user, "EXPERT_REQUEST_CREATE", "expert_request", req.id)
    return _to_out(db, req)


@router.get("/requests", response_model=list[ExpertRequestOut])
def list_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(ExpertRequest).order_by(ExpertRequest.created_at.desc())
    if user.role == "user":
        stmt = stmt.where(ExpertRequest.user_id == user.id)
    if status_filter:
        stmt = stmt.where(ExpertRequest.status == status_filter.upper())
    return [_to_out(db, req) for req in db.scalars(stmt)]


@router.get("/requests/{request_id}", response_model=ExpertRequestOut)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.get(ExpertRequest, request_id)
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    if user.role == "user" and req.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request")
    return _to_out(db, req)


@router.patch("/requests/{request_id}", response_model=ExpertRequestOut)
def update_request(
    request_id: int,
    data: ExpertRequestUpdate,
    db: Session = Depends(get_db),
    _expert: User = Depends(require_roles("expert", "admin")),
):
    req = db.get(ExpertRequest, request_id)
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    if data.status is not None:
        req.status = data.status
    if data.priority is not None:
        req.priority = data.priority
    if data.resolution is not None:
        req.resolution = data.resolution
    if req.status in ("RESOLVED", "CLOSED") and req.resolved_at is None:
        req.resolved_at = datetime.now(timezone.utc)
    if req.assigned_expert_id is None:
        req.assigned_expert_id = _expert.id

    db.commit()
    db.refresh(req)
    write_audit(
        db,
        _expert,
        "EXPERT_REQUEST_UPDATE",
        "expert_request",
        req.id,
        {"status": req.status, "priority": req.priority},
    )
    return _to_out(db, req)