"""Pydantic схемы для аутентификации."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Запрос логина."""

    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class RegisterRequest(BaseModel):
    """Запрос регистрации."""

    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    invite_code: str = Field(min_length=1, max_length=50)


class TokenResponse(BaseModel):
    """Ответ с токеном."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Ответ с данными пользователя."""

    id: int
    username: str
    avatar_path: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    """Запрос обновления профиля."""

    username: str | None = Field(default=None, min_length=2, max_length=50)


class GenerateInviteResponse(BaseModel):
    """Ответ с invite-кодом."""

    code: str


class UserSearchResponse(BaseModel):
    """Ответ с данными пользователя для поиска."""

    id: int
    username: str
    is_active: bool

    model_config = {"from_attributes": True}
