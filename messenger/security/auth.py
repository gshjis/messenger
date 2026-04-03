"""Модуль безопасности: JWT и хеширование паролей."""

from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from messenger.config import settings

# Argon2 hasher
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Хеширование пароля через argon2id."""
    return password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Проверка пароля."""
    try:
        return password_hasher.verify(hashed_password, password)
    except VerifyMismatchError:
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Создание JWT токена."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    """Декодирование JWT токена."""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def generate_invite_code() -> str:
    """Генерация случайного invite-кода."""
    import secrets
    import string

    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(settings.invite_code_length))
