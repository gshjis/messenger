"""Конфигурация и фикстуры для pytest."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.database import get_session
from messenger.main import app
from messenger.models.user import User


# Тестовая БД в памяти
TEST_DB_URL = "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Создание event loop для сессии тестов."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    """Создание тестового движка БД."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Создание тестовой сессии БД."""
    async with AsyncSession(test_engine) as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """Асинхронный HTTP клиент для тестов API."""

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSession(test_engine) as session:
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
    from argon2 import PasswordHasher

    ph = PasswordHasher()
    user = User(
        username=test_user_data["username"],
        hashed_password=ph.hash(test_user_data["password"]),
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
def mock_password_hasher() -> MagicMock:
    """Мок для argon2 PasswordHasher."""
    return MagicMock()


@pytest.fixture
def mock_file_validator() -> MagicMock:
    """Мок для валидации файлов."""
    return MagicMock()
