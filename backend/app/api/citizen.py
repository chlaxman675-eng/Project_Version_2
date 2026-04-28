"""Citizen-facing endpoints (SOS, reporting, safe zones)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.database import get_session
from app.db.models import CitizenReport, Pole, User
from app.engine.incident_pipeline import pipeline
from app.prediction.heatmap import heatmap_engine

router = APIRouter()


class SOSIn(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    note: str | None = None
    pole_id: str | None = None


class ReportIn(BaseModel):
    description: str
    latitude: float | None = None
    longitude: float | None = None


@router.post("/sos")
async def sos(
    body: SOSIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    rep = CitizenReport(
        user_id=user.id, kind="sos", description=body.note or "Citizen SOS",
        latitude=body.latitude, longitude=body.longitude,
    )
    session.add(rep)
    await session.commit()
    await pipeline.trigger_panic(body.pole_id, body.latitude, body.longitude, reporter=user.email)
    return {"ok": True, "report_id": rep.id}


@router.post("/sos/anonymous")
async def sos_anonymous(body: SOSIn, session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    """Anonymous SOS for unauthenticated demo flows."""
    rep = CitizenReport(
        user_id=None, kind="sos",
        description=body.note or "Anonymous Citizen SOS",
        latitude=body.latitude, longitude=body.longitude,
    )
    session.add(rep)
    await session.commit()
    await pipeline.trigger_panic(body.pole_id, body.latitude, body.longitude, reporter="anonymous")
    return {"ok": True, "report_id": rep.id}


@router.post("/report")
async def report(
    body: ReportIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    rep = CitizenReport(
        user_id=user.id, kind="report", description=body.description,
        latitude=body.latitude, longitude=body.longitude,
    )
    session.add(rep)
    await session.commit()
    return {"ok": True, "report_id": rep.id}


@router.get("/safe-zones")
async def safe_zones(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    """Return poles plus inverted risk zones (low-risk = safer)."""
    poles = (await session.execute(select(Pole))).scalars().all()
    risk = await heatmap_engine.compute(session)
    safe = sorted(risk, key=lambda c: c.risk)[:5]
    return {
        "poles": [
            {"id": p.id, "name": p.name, "lat": p.latitude, "lon": p.longitude, "zone": p.zone,
             "status": p.status} for p in poles
        ],
        "low_risk_areas": [c.__dict__ for c in safe],
    }


@router.get("/safe-route")
async def safe_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    from_lat: float, from_lon: float, to_lat: float, to_lon: float,
) -> dict:
    """Suggests a 'risk-aware' detour: a midpoint biased toward the lowest-risk
    pole within the bounding box."""
    poles = (await session.execute(select(Pole))).scalars().all()
    risk_cells = await heatmap_engine.compute(session)
    risk_lookup = {(round(c.lat, 3), round(c.lon, 3)): c.risk for c in risk_cells}

    midpoint = ((from_lat + to_lat) / 2, (from_lon + to_lon) / 2)
    candidates = [p for p in poles if min(from_lat, to_lat) - 0.02 <= p.latitude <= max(from_lat, to_lat) + 0.02]
    candidates = candidates or poles
    if candidates:
        safest = min(
            candidates,
            key=lambda p: risk_lookup.get((round(p.latitude, 3), round(p.longitude, 3)), 0.0),
        )
        waypoint = (safest.latitude, safest.longitude)
    else:
        waypoint = midpoint

    return {
        "from": {"lat": from_lat, "lon": from_lon},
        "to": {"lat": to_lat, "lon": to_lon},
        "waypoint": {"lat": waypoint[0], "lon": waypoint[1]},
        "policy": "lowest_risk_pole_waypoint",
    }
