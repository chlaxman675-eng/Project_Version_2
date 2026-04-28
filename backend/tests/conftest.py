"""Pytest fixtures."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

# Make the repo root and backend importable.
_HERE = Path(__file__).resolve()
_BACKEND = _HERE.parent.parent
_REPO = _BACKEND.parent
for p in (_BACKEND, _REPO):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Use an isolated test DB that doesn't collide with dev data.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./surakshanet_test.db")
os.environ.setdefault("ENABLE_SIMULATION_ON_STARTUP", "false")
# Force the lightweight mock detector for tests so we don't download YOLO weights.
os.environ.setdefault("ENABLE_YOLO", "false")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
