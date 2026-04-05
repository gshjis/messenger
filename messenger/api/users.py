"""Роутеры для управления пользователями."""

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.api.auth import get_current_user
from messenger.database import get_session
from messenger.models.user import User
from messenger.schemas.auth import UserSearchResponse

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/search", response_model=list[UserSearchResponse])
async def search_users(
    q: str = Query(min_length=1, max_length=50, description="Поисковый запрос (часть username)"),
    limit: int = Query(20, ge=1, le=100, description="Максимальное количество результатов"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[UserSearchResponse]:
    """Поиск пользователей по username.
    
    Возвращает список активных пользователей, чей username содержит
    указанную подстроку (case-insensitive поиск).
    """
    assert current_user.id is not None
    
    # Экранирование спецсимволов LIKE
    escaped_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    
    result = await session.exec(
        select(User).where(
            User.username.like(f"%{escaped_q}%"),  # type: ignore[arg-type]
            User.is_active == True,  # noqa: E712
            User.id != current_user.id,  # Исключаем текущего пользователя
        ).limit(limit)
    )
    users = result.all()
    
    return [
        UserSearchResponse(
            id=user.id,  # type: ignore[arg-type]
            username=user.username,
            is_active=user.is_active,
        )
        for user in users
    ]
