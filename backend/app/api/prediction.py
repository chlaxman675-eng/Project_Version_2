"""Crime prediction endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.prediction.heatmap import heatmap_engine

router = APIRouter()


@router.get("/heatmap")
async def heatmap(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    cells = await heatmap_engine.compute(session)
    return {"cells": [c.__dict__ for c in cells], "count": len(cells)}


@router.get("/risk-zones")
async def risk_zones(
    session: Annotated[AsyncSession, Depends(get_session)],
    top_n: int = 5,
) -> dict:
    zones = await heatmap_engine.risk_zones(session, top_n=top_n)
    return {"zones": zones}


@router.get("/patrol-recommendations")
async def patrol_recommendations(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    plan = await heatmap_engine.patrol_recommendations(session)
    return {"plan": plan}
