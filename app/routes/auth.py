import jwt
import bcrypt
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_session
from app.models import User
from app.config import load_config

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("mineadmin.auth")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: int, username: str, is_admin: bool) -> str:
    cfg = load_config()
    payload = {
        "user_id": user_id,
        "username": username,
        "is_admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, cfg["secret_key"], algorithm="HS256")


def decode_token(token: str) -> dict:
    cfg = load_config()
    try:
        return jwt.decode(token, cfg["secret_key"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    else:
        token = request.cookies.get("token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(token)


@router.post("/setup")
async def setup(request: Request, session: AsyncSession = Depends(get_session)):
    count = await session.execute(select(func.count(User.id)))
    if count.scalar() > 0:
        raise HTTPException(status_code=400, detail="Setup already completed")

    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    user = User(
        username=username,
        password_hash=hash_password(password),
        is_admin=True
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_token(user.id, user.username, user.is_admin)
    return {"token": token, "user": {"id": user.id, "username": user.username, "is_admin": True}}


@router.post("/login")
async def login(request: Request, session: AsyncSession = Depends(get_session)):
    data = await request.json()
    username = data.get("username", "")
    password = data.get("password", "")

    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user.id, user.username, user.is_admin)
    return {"token": token, "user": {"id": user.id, "username": user.username, "is_admin": user.is_admin}}


@router.get("/check")
async def check_auth(user: dict = Depends(get_current_user)):
    return {"authenticated": True, "user": user}


@router.get("/needs-setup")
async def needs_setup(session: AsyncSession = Depends(get_session)):
    count = await session.execute(select(func.count(User.id)))
    return {"needs_setup": count.scalar() == 0}
