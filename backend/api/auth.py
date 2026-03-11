from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, EmailStr

from database import get_db
from models.auth_user import AuthUser
from services.auth import hash_password, verify_password, create_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class RegisterBody(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str


class LoginBody(BaseModel):
    account: str  # username or email
    password: str


@router.post("/register")
async def register(body: RegisterBody, db: AsyncSession = Depends(get_db)):
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    exists = await db.execute(
        select(AuthUser.id).where(
            or_(AuthUser.username == body.username, AuthUser.email == body.email)
        ).limit(1)
    )
    if exists.scalar() is not None:
        raise HTTPException(status_code=400, detail="Username or email already exists")

    user = AuthUser(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email}


@router.post("/login")
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuthUser).where(
            or_(AuthUser.username == body.account, AuthUser.email == body.account)
        ).limit(1)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_token(user.id)
    return {
        "token": token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.get("/me")
async def me(current_user: AuthUser = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "email": current_user.email}
