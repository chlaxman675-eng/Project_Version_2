"""Dispatch endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_roles
from app.db.database import get_session
from app.db.models import DispatchAssignment, Incident, User
from app.dispatch.recommender import DEMO_UNITS, DispatchRecommender
from app.engine.event_bus import bus
from app.services.audit import audit

router = APIRouter()
_recommender = DispatchRecommender()


class AssignmentIn(BaseModel):
    incident_id: int
    unit_id: str
    notes: str = ""


class AssignmentOut(BaseModel):
    id: int
    incident_id: int
    unit_id: str
    status: str
    eta_seconds: int
    notes: str
    created_at: datetime
    updated_at: datetime


class StatusUpdate(BaseModel):
    status: str


@router.get("/units")
async def list_units() -> list[dict]:
    return [
        {"unit_id": u.unit_id, "kind": u.kind, "lat": u.latitude, "lon": u.longitude,
         "available": u.available}
        for u in DEMO_UNITS
    ]


@router.get("/assignments", response_model=list[AssignmentOut])
async def list_assignments(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 100,
) -> list[AssignmentOut]:
    rows = (await session.execute(
        select(DispatchAssignment).order_by(DispatchAssignment.created_at.desc()).limit(limit)
    )).scalars().all()
    return [AssignmentOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/assign", response_model=AssignmentOut, status_code=201)
async def assign(
    body: AssignmentIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_roles("operator", "police", "admin"))],
) -> AssignmentOut:
    inc = (await session.execute(select(Incident).where(Incident.id == body.incident_id))).scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")
    rec = _recommender.recommend(inc)
    eta = next((u["eta_seconds"] for u in rec.get("units", []) if u["unit_id"] == body.unit_id), 600)
    assignment = DispatchAssignment(
        incident_id=body.incident_id, unit_id=body.unit_id,
        status="dispatched", eta_seconds=eta, notes=body.notes,
    )
    session.add(assignment)
    inc.status = "dispatched"
    await audit(session, user.email, "dispatch.assigned", f"incident:{inc.id}",
                metadata={"unit_id": body.unit_id, "eta_seconds": eta})
    await session.commit()
    await session.refresh(assignment)
    await bus.publish("dispatch.assigned", {
        "assignment_id": assignment.id,
        "incident_id": inc.id,
        "unit_id": body.unit_id,
        "eta_seconds": eta,
        "by": user.email,
    })
    return AssignmentOut.model_validate(assignment, from_attributes=True)


@router.post("/assignments/{assignment_id}/status", response_model=AssignmentOut)
async def update_assignment(
    assignment_id: int, body: StatusUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_roles("operator", "police", "admin"))],
) -> AssignmentOut:
    a = (await session.execute(
        select(DispatchAssignment).where(DispatchAssignment.id == assignment_id)
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="assignment not found")
    if body.status not in {"dispatched", "en_route", "on_scene", "cleared"}:
        raise HTTPException(status_code=400, detail="invalid status")
    a.status = body.status
    a.updated_at = datetime.now(timezone.utc)
    if body.status == "cleared":
        inc = (await session.execute(select(Incident).where(Incident.id == a.incident_id))).scalar_one_or_none()
        if inc and inc.status != "resolved":
            inc.status = "resolved"
            inc.resolved_at = datetime.now(timezone.utc)
    await audit(session, user.email, "dispatch.status_change", f"assignment:{a.id}",
                metadata={"status": body.status})
    await session.commit()
    await session.refresh(a)
    await bus.publish("dispatch.updated", {"assignment_id": a.id, "status": a.status})
    return AssignmentOut.model_validate(a, from_attributes=True)
