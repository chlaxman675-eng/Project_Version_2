"""CLI demo: cycles through every scenario and prints resulting incidents.

Usage::

    python -m simulations.run_demo

Run the backend separately first (``uvicorn app.main:app``) so the demo can
share the same database, or rely on the in-process pipeline.
"""
from __future__ import annotations

import asyncio

from app.db.database import init_db
from app.engine.incident_pipeline import pipeline, seed_default_poles
from simulations.scenarios import SCENARIOS, inject_scenario


async def main() -> None:
    await init_db()
    await seed_default_poles()
    for scenario_id in SCENARIOS:
        result = await inject_scenario(pipeline, scenario_id)
        print(f"[{scenario_id}] -> {result}")
        await asyncio.sleep(0.3)


if __name__ == "__main__":
    asyncio.run(main())
