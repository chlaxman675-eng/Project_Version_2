"""Auth + seed tests (regression for bcrypt 72-byte limit)."""
from __future__ import annotations

import httpx
import pytest

from app.auth.security import hash_password, verify_password
from app.db.database import init_db
from app.main import _seed_admin, app


def test_hash_and_verify_short_and_long():
    assert verify_password("password123", hash_password("password123"))
    long_pw = "x" * 200  # would normally trip bcrypt's 72-byte limit
    assert verify_password(long_pw, hash_password(long_pw))


def test_seed_admin_does_not_raise():
    import asyncio

    async def go():
        await init_db()
        await _seed_admin()

    asyncio.run(go())


@pytest.mark.asyncio
async def test_login_demo_account():
    await init_db()
    await _seed_admin()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/auth/login",
            data={"username": "operator@suraksha.local", "password": "Operator123!"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["role"] == "operator"
        assert body["access_token"]
