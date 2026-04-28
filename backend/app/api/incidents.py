"""Incident management endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_roles
from app.db.database import get_session
from app.db.models import Incident, User

router = APIRouter()


class IncidentOut(BaseModel):
    id: int
    pole_id: str | None
    type: str
    severity: str
    score: float
    status: str
    description: str
    latitude: float | None
    longitude: float | None
    sources: dict
    created_at: datetime
    resolved_at: datetime | None


@router.get("", response_model=list[IncidentOut])
async def list_incidents(
    session: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
) -> list[IncidentOut]:
    stmt = select(Incident).order_by(Incident.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Incident.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return [IncidentOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/{incident_id}", response_model=IncidentOut)
async def get_incident(
    incident_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IncidentOut:
    inc = (await session.execute(select(Incident).where(Incident.id == incident_id))).scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")
    return IncidentOut.model_validate(inc, from_attributes=True)


class StatusUpdate(BaseModel):
    status: str


@router.post("/{incident_id}/status", response_model=IncidentOut)
async def update_status(
    incident_id: int,
    body: StatusUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_roles("operator", "police", "admin"))],
) -> IncidentOut:
    inc = (await session.execute(select(Incident).where(Incident.id == incident_id))).scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")
    if body.status not in {"open", "dispatched", "resolved", "false_positive"}:
        raise HTTPException(status_code=400, detail="invalid status")
    inc.status = body.status
    if body.status in {"resolved", "false_positive"}:
        inc.resolved_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(inc)
    return IncidentOut.model_validate(inc, from_attributes=True)
