"""Endpoints to drive the live simulation engine."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import require_roles
from app.db.models import User
from app.engine.incident_pipeline import pipeline
from simulations.scenarios import inject_scenario, list_scenarios

router = APIRouter()


@router.get("/scenarios")
async def scenarios() -> list[dict]:
    return list_scenarios()


class InjectIn(BaseModel):
    scenario: str
    pole_id: str | None = None


@router.post("/inject")
async def inject(
    body: InjectIn,
    user: Annotated[User, Depends(require_roles("operator", "admin"))],
) -> dict:
    return await inject_scenario(pipeline, body.scenario, pole_id=body.pole_id)


@router.post("/inject-public")
async def inject_public(body: InjectIn) -> dict:
    """Unauthenticated injection for demo / tests. Use with care."""
    return await inject_scenario(pipeline, body.scenario, pole_id=body.pole_id)


@router.post("/start")
async def start(user: Annotated[User, Depends(require_roles("operator", "admin"))]) -> dict:
    await pipeline.start()
    return {"running": True}


@router.post("/stop")
async def stop(user: Annotated[User, Depends(require_roles("operator", "admin"))]) -> dict:
    await pipeline.stop()
    return {"running": False}
