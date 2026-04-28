"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="citizen", nullable=False)
    # citizen | operator | police | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Pole(Base):
    """Smart surveillance pole node."""

    __tablename__ = "poles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    zone: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="online", nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Incident(Base):
    """An anomaly / threat event detected by the system."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pole_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("poles.id"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # violence | intrusion | crowd_anomaly | abandoned_object | gunshot | scream | panic_sos
    severity: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    # open | dispatched | resolved | false_positive
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    sources: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # {"vision": 0.8, "audio": 0.3, "motion": 1.0, ...}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    alerts: Mapped[list[Alert]] = relationship(back_populates="incident", cascade="all,delete")


class Alert(Base):
    """Outbound alert generated from an incident."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id"), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), default="dashboard", nullable=False)
    # dashboard | police | citizen | sms | push
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    delivered: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    incident: Mapped[Incident] = relationship(back_populates="alerts")


class DispatchAssignment(Base):
    __tablename__ = "dispatch_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id"), index=True, nullable=False)
    unit_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="dispatched", nullable=False)
    # dispatched | en_route | on_scene | cleared
    eta_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class CitizenReport(Base):
    __tablename__ = "citizen_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default="report", nullable=False)
    # report | sos
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(255), default="system", nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
