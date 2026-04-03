"""Модель чата (личный или групповой)."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class ChatType(str, Enum):
    """Тип чата."""

    personal = "personal"
    group = "group"


class Chat(SQLModel, table=True):
    """Чат (личный или групповой)."""

    __tablename__ = "chats"

    id: int | None = Field(default=None, primary_key=True)
    type: ChatType = Field(default=ChatType.personal)
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    avatar_path: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
