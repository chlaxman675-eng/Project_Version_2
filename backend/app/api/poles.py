"""Pole listing endpoint."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import Pole

router = APIRouter()


@router.get("")
async def list_poles(session: Annotated[AsyncSession, Depends(get_session)]) -> list[dict]:
    rows = (await session.execute(select(Pole))).scalars().all()
    return [
        {"id": p.id, "name": p.name, "lat": p.latitude, "lon": p.longitude,
         "zone": p.zone, "status": p.status,
         "last_seen": p.last_seen.isoformat()}
        for p in rows
    ]
