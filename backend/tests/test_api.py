"""End-to-end smoke tests for the public API."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.db.database import init_db, session_scope
from app.db.models import Incident
from app.engine.incident_pipeline import pipeline, seed_default_poles
from app.main import app
from simulations.scenarios import inject_scenario


@pytest.mark.asyncio
async def test_root_and_metrics():
    await init_db()
    await seed_default_poles()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/")
        assert r.status_code == 200
        r = await client.get("/api/telemetry/metrics")
        assert r.status_code == 200
        body = r.json()
        assert "incidents_total" in body
        assert body["poles_total"] >= 5


@pytest.mark.asyncio
async def test_scenario_creates_incident():
    await init_db()
    await seed_default_poles()
    result = await inject_scenario(pipeline, "violent_fight")
    assert result["ok"]
    # let the materialiser flush
    await asyncio.sleep(0.05)
    async with session_scope() as session:
        rows = (await session.execute(__import__("sqlalchemy").select(Incident))).scalars().all()
        assert any(r.type in {"violence", "scream"} for r in rows)


@pytest.mark.asyncio
async def test_panic_scenario_creates_critical_incident():
    await init_db()
    await seed_default_poles()
    result = await inject_scenario(pipeline, "panic_button")
    assert result["ok"]
    await asyncio.sleep(0.05)
    async with session_scope() as session:
        rows = (await session.execute(__import__("sqlalchemy").select(Incident))).scalars().all()
        assert any(r.type == "panic_sos" and r.severity == "critical" for r in rows)
