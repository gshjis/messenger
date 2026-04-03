"""Модель invite-кода для регистрации."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class InviteCode(SQLModel, table=True):
    """Код приглашения для регистрации."""

    __tablename__ = "invite_codes"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True, max_length=50)
    max_uses: int = Field(default=1)
    used_count: int = Field(default=0)
    created_by: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = Field(default=None)
    is_active: bool = Field(default=True)
