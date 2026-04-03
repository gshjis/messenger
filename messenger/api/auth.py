"""Роутеры аутентификации."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from loguru import logger
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.config import settings
from messenger.database import get_session
from messenger.models.invite_code import InviteCode
from messenger.models.user import User
from messenger.schemas.auth import (
    GenerateInviteResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from messenger.security.auth import (
    create_access_token,
    decode_access_token,
    generate_invite_code,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def get_current_user(
    token: str | None = Cookie(default=None, alias="access_token"),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Получение текущего пользователя из JWT cookie."""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id: int | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await session.exec(select(User).where(User.id == user_id))
    user = result.first()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    if user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is banned")

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """Логин пользователя."""
    result = await session.exec(select(User).where(User.username == request.username))
    user = result.first()

    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is banned")

    # Создание токена
    token = create_access_token(data={"sub": user.id})

    # Установка HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )

    logger.info(f"User {user.username} logged in")
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """Регистрация по invite-коду."""
    # Проверка invite-кода
    result = await session.exec(select(InviteCode).where(InviteCode.code == request.invite_code))
    invite = result.first()

    if invite is None or not invite.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite code")

    if invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite code has been fully used")

    # Проверка уникальности username
    existing = await session.exec(select(User).where(User.username == request.username))
    if existing.first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    # Создание пользователя
    user = User(
        username=request.username,
        hashed_password=hash_password(request.password),
    )
    session.add(user)

    # Обновление invite-кода
    invite.used_count += 1
    if invite.used_count >= invite.max_uses:
        invite.is_active = False

    await session.commit()
    await session.refresh(user)

    # Создание токена
    token = create_access_token(data={"sub": user.id})

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )

    logger.info(f"New user registered: {user.username}")
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Получение данных текущего пользователя."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Обновление профиля (смена ника)."""
    if request.username is not None:
        # Проверка уникальности
        existing = await session.exec(
            select(User).where(User.username == request.username, User.id != current_user.id)
        )
        if existing.first() is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

        current_user.username = request.username

    await session.add(current_user)
    await session.commit()
    await session.refresh(current_user)

    logger.info(f"User {current_user.id} updated profile")
    return current_user


@router.post("/invite", response_model=GenerateInviteResponse)
async def generate_invite(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Генерация нового invite-кода."""
    code = generate_invite_code()
    invite = InviteCode(code=code, created_by=current_user.id)
    session.add(invite)
    await session.commit()
    await session.refresh(invite)

    logger.info(f"User {current_user.id} generated invite code")
    return GenerateInviteResponse(code=invite.code)


@router.post("/logout")
async def logout(response: Response):
    """Выход (удаление cookie)."""
    response.delete_cookie(key="access_token")
    return {"message": "Logged out"}
