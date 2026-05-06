"""Application configuration."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables / .env."""

    app_name: str = "SurakshaNet AI"
    environment: str = "development"
    api_prefix: str = "/api"

    # Auth
    jwt_secret: str = "change-me-in-production-this-is-only-for-dev"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # Database
    database_url: str = "sqlite+aiosqlite:///./surakshanet.db"

    # AI / inference
    # YOLOv8n weights (~6MB) auto-download on first inference. Set to False to
    # force the rule-based MockVisionDetector (e.g. air-gapped environments).
    enable_yolo: bool = True
    yolo_model: str = "yolov8n.pt"
    detection_confidence_threshold: float = 0.55
    fusion_alert_threshold: float = 0.65

    # Simulation
    simulation_tick_seconds: float = 2.0
    enable_simulation_on_startup: bool = True

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173", "http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
