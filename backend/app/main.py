"""FastAPI entrypoint for SurakshaNet AI."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import select

from app.api import api_router
from app.auth.security import hash_password
from app.config import get_settings
from app.db.database import init_db, session_scope
from app.db.models import User
from app.engine.incident_pipeline import pipeline, seed_default_poles

settings = get_settings()


async def _seed_admin() -> None:
    """Create a default admin + demo users for the MVP."""
    demo = [
        ("admin@suraksha.local", "SurakshaAdmin123!", "Suraksha Admin", "admin"),
        ("operator@suraksha.local", "Operator123!", "Control Room Operator", "operator"),
        ("officer@suraksha.local", "Police123!", "Officer Reddy", "police"),
        ("citizen@suraksha.local", "Citizen123!", "Demo Citizen", "citizen"),
    ]
    async with session_scope() as session:
        for email, pw, full_name, role in demo:
            existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not existing:
                session.add(User(email=email, full_name=full_name,
                                 hashed_password=hash_password(pw), role=role))
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting {} ({})", settings.app_name, settings.environment)
    await init_db()
    await _seed_admin()
    await seed_default_poles()
    if settings.enable_simulation_on_startup:
        await pipeline.start()
    try:
        yield
    finally:
        await pipeline.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Smart Predictive Public Safety Platform — backend API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict:
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "environment": settings.environment,
        "docs": "/docs",
        "ws": "/api/ws",
    }
