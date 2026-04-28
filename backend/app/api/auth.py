"""Auth endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.security import create_access_token, hash_password, verify_password
from app.db.database import get_session
from app.db.models import User

router = APIRouter()


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "citizen"


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str


@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterIn, session: Annotated[AsyncSession, Depends(get_session)]) -> UserOut:
    exists = (await session.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="email already registered")
    if body.role not in {"citizen", "operator", "police", "admin"}:
        raise HTTPException(status_code=400, detail="invalid role")
    user = User(email=body.email, full_name=body.full_name,
                hashed_password=hash_password(body.password), role=body.role)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserOut(id=user.id, email=user.email, full_name=user.full_name, role=user.role)


@router.post("/login", response_model=TokenOut)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenOut:
    user = (await session.execute(select(User).where(User.email == form.username))).scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    token = create_access_token(user.email, user.role)
    return TokenOut(access_token=token, role=user.role, email=user.email)


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut(id=user.id, email=user.email, full_name=user.full_name, role=user.role)
