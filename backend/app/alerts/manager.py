"""Alert generation and channel routing."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert, Incident


class AlertManager:
    """Creates DB-backed alerts and would route to channels (push/SMS) in prod."""

    SEVERITY_CHANNELS: dict[str, list[str]] = {
        "critical": ["dashboard", "police", "citizen", "push"],
        "high": ["dashboard", "police", "push"],
        "medium": ["dashboard", "police"],
        "low": ["dashboard"],
    }

    async def generate(
        self,
        session: AsyncSession,
        incident: Incident,
        recommendation: dict[str, Any] | None = None,
    ) -> Alert:
        channels = self.SEVERITY_CHANNELS.get(incident.severity, ["dashboard"])
        primary = channels[0]
        payload = {
            "channels": channels,
            "headline": f"[{incident.severity.upper()}] {incident.type.replace('_', ' ').title()}",
            "score": incident.score,
            "pole_id": incident.pole_id,
            "recommendation": recommendation or {},
        }
        alert = Alert(
            incident_id=incident.id,
            channel=primary,
            payload=payload,
            delivered=True,  # MVP: dashboard is delivery
        )
        session.add(alert)
        await session.flush()
        return alert
