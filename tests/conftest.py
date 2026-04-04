"""Конфигурация и фикстуры для pytest."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.database import get_session
from messenger.main import app
from messenger.models.user import User
from messenger.security.auth import create_access_token, hash_password


# Глобальный тестовый движок (один на все тесты)
_test_engine = None


def get_test_engine():
    """Получить или создать тестовый движок (singleton)."""
    global _test_engine
    if _test_engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import StaticPool

        _test_engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return _test_engine


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Создать таблицы в тестовой БД один раз на сессию."""
    import asyncio
    engine = get_test_engine()

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_setup())
    yield


async def _clear_all_tables(session: AsyncSession) -> None:
    """Очистить все таблицы."""
    await session.execute(text("DELETE FROM messages"))
    await session.execute(text("DELETE FROM chat_members"))
    await session.execute(text("DELETE FROM chats"))
    await session.execute(text("DELETE FROM invite_codes"))
    await session.execute(text("DELETE FROM users"))
    await session.commit()


@pytest_asyncio.fixture
async def test_session() -> AsyncGenerator[AsyncSession, None]:
    """Создание тестовой сессии БД."""
    engine = get_test_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await _clear_all_tables(session)
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Асинхронный HTTP клиент для тестов API."""
    engine = get_test_engine()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data() -> dict:
    """Данные тестового пользователя."""
    return {
        "username": "testuser",
        "password": "SecurePass123!",
    }


@pytest_asyncio.fixture
async def test_user(test_session: AsyncSession, test_user_data) -> User:
    """Создание тестового пользователя в БД."""
    user = User(
        username=test_user_data["username"],
        hashed_password=hash_password(test_user_data["password"]),
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_client(test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Клиент с авторизацией через Authorization header."""
    assert test_user.id is not None
    token = create_access_token(data={"sub": test_user.id})

    engine = get_test_engine()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
