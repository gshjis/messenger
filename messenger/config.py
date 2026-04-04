"""Конфигурация приложения из переменных окружения."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из .env файла."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Приложение
    app_name: str = "Messenger"
    debug: bool = False
    log_level: str = "INFO"

    # База данных
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 дней

    # Файлы
    upload_dir: str = "./data/uploads"
    max_file_size_mb: int = 25
    allowed_mime_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
        "application/zip",
        "text/plain",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]

    # Invite-коды
    invite_code_length: int = 8
    invite_code_max_uses: int = 1

    # Rate limiting
    rate_limit_requests: int = 5
    rate_limit_seconds: int = 1

    # CORS (разрешённые origins)
    cors_origins: list[str] = ["http://localhost", "http://localhost:5173"]

    # Админ
    admin_invite_code: str = "ADMIN-SETUP-CODE"

    @model_validator(mode="after")
    def check_jwt_secret(self) -> "Settings":
        """Проверка что JWT secret изменён в production."""
        if self.jwt_secret_key == "change-me-in-production" and not self.debug:
            raise ValueError("JWT_SECRET_KEY must be changed in production. Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'")
        return self


settings = Settings()
