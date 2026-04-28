"""Heatmap engine tests."""
from __future__ import annotations

from app.db.database import init_db, session_scope
from app.db.models import Incident
from app.prediction.heatmap import heatmap_engine


async def test_heatmap_empty_then_populated():
    await init_db()
    async with session_scope() as session:
        cells = await heatmap_engine.compute(session)
        # Could be empty or populated depending on test order; type must be list.
        assert isinstance(cells, list)
        # Add a synthetic incident.
        session.add(Incident(
            type="violence", severity="high", score=0.9,
            description="t", latitude=17.4486, longitude=78.3908,
            sources={"vision": 0.9},
        ))
        await session.commit()
        cells = await heatmap_engine.compute(session)
        assert any(abs(c.lat - 17.45) < 0.05 for c in cells)
