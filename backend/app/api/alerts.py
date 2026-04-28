"""Alerts feed."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import Alert

router = APIRouter()


class AlertOut(BaseModel):
    id: int
    incident_id: int
    channel: str
    payload: dict
    delivered: bool
    created_at: datetime


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 100,
) -> list[AlertOut]:
    rows = (await session.execute(select(Alert).order_by(Alert.created_at.desc()).limit(limit))).scalars().all()
    return [AlertOut.model_validate(r, from_attributes=True) for r in rows]
