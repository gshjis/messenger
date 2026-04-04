"""Точка входа FastAPI приложения."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from messenger.api.auth import router as auth_router
from messenger.api.chat import router as chat_router
from messenger.api.files import router as files_router
from messenger.config import settings
from messenger.database import init_db
from messenger.websockets.handler import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Инициализация и завершение работы приложения."""
    logger.info("Starting messenger...")

    # Создание директорий
    Path("./data").mkdir(parents=True, exist_ok=True)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    # Инициализация БД
    await init_db()
    logger.info("Database initialized")

    yield

    logger.info("Shutting down messenger...")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(files_router)
app.include_router(ws_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Endpoint проверки работоспособности."""
    return {"status": "ok", "version": "0.1.0"}
