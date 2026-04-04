"""Настройка базы данных и сессий."""

from collections.abc import AsyncGenerator
from pathlib import Path

import aiosqlite
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.config import settings

# Путь к файлу БД
DB_DIR = Path("./data")
DB_FILE = DB_DIR / "app.db"

# Глобальный движок (ленивая инициализация)
_engine = None


def get_engine():
    """Получить или создать движок БД (singleton)."""
    global _engine
    if _engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine

        _engine = create_async_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
    return _engine


async def init_db() -> None:
    """Инициализация БД: создание таблиц и настройка WAL режима."""
    DB_DIR.mkdir(parents=True, exist_ok=True)

    # Настройка WAL режима для SQLite
    async with aiosqlite.connect(str(DB_FILE)) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.commit()

    # Создание таблиц через SQLModel (используем единый движок)
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Получить сессию БД (dependency для FastAPI)."""
    engine = get_engine()
    async with AsyncSession(engine) as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
