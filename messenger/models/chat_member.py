"""Модель участника чата."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class MemberRole(str, Enum):
    """Роль участника чата."""

    admin = "admin"
    member = "member"


class ChatMember(SQLModel, table=True):
    """Связь пользователя с чатом."""

    __tablename__ = "chat_members"

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(foreign_key="chats.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    role: MemberRole = Field(default=MemberRole.member)
    joined_at: datetime = Field(default_factory=datetime.utcnow)
