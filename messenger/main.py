"""Точка входа FastAPI приложения."""

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from messenger.api.auth import router as auth_router
from messenger.api.chat import router as chat_router
from messenger.api.files import router as files_router
from messenger.config import settings
from messenger.database import init_db
from messenger.websockets.handler import router as ws_router

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_requests}/{settings.rate_limit_seconds}s"],
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Инициализация и завершение работы приложения."""
    logger.info("Starting messenger...")
    logger.info(f"Log level: {settings.log_level}")
    logger.info(f"Debug mode: {settings.debug}")

    # Настройка логирования
    logger.remove(0)
    logger.add(
        "stderr",
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    # Логи в файл — только если директория доступна для записи
    log_dir = Path("./data/logs")
    if log_dir.exists() or log_dir.mkdir(parents=True, exist_ok=True):
        logger.add(
            log_dir / "messenger_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            level="INFO",
            enqueue=True,
        )

    # Создание директорий
    Path("./data").mkdir(parents=True, exist_ok=True)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path("./data/logs").mkdir(parents=True, exist_ok=True)

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

# Rate limiting exception handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Обработчик превышения rate limit."""
    return Response(
        content='{"detail": "Rate limit exceeded. Try again later."}',
        status_code=429,
        media_type="application/json",
    )


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)


@app.middleware("http")
async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Добавление security headers к каждому ответу."""
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Убираем серверный header (информационная утечка)
    if "server" in response.headers:
        del response.headers["server"]

    return response


# Роутеры (без rate limit на health и WebSocket)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(files_router)
app.include_router(ws_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Endpoint проверки работоспособности."""
    return {"status": "ok", "version": "0.1.0"}
