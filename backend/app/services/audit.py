"""Audit logging."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


async def audit(
    session: AsyncSession,
    actor: str,
    action: str,
    target: str = "",
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    log = AuditLog(actor=actor, action=action, target=target, metadata_json=metadata or {})
    session.add(log)
    await session.flush()
    return log
