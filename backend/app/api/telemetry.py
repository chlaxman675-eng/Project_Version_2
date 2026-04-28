"""System telemetry / metrics endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import Alert, Incident, Pole
from app.engine.incident_pipeline import pipeline

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/metrics")
async def metrics(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    # DB-derived numbers
    total_incidents = (await session.execute(select(func.count(Incident.id)))).scalar() or 0
    open_incidents = (await session.execute(
        select(func.count(Incident.id)).where(Incident.status == "open")
    )).scalar() or 0
    total_alerts = (await session.execute(select(func.count(Alert.id)))).scalar() or 0
    total_poles = (await session.execute(select(func.count(Pole.id)))).scalar() or 0

    pipe_metrics = pipeline.metrics()
    pipe_metrics.update({
        "incidents_total": total_incidents,
        "incidents_open": open_incidents,
        "alerts_total": total_alerts,
        "poles_total": total_poles,
    })
    return pipe_metrics
