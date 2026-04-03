"""Модель сообщения."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class MessageStatus(str, Enum):
    """Статус сообщения."""

    sent = "sent"
    delivered = "delivered"
    read = "read"


class Message(SQLModel, table=True):
    """Сообщение в чате."""

    __tablename__ = "messages"

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(foreign_key="chats.id", index=True)
    sender_id: int = Field(foreign_key="users.id", index=True)
    content: str | None = Field(default=None, max_length=10000)
    file_path: str | None = Field(default=None, max_length=500)
    file_mime: str | None = Field(default=None, max_length=100)
    file_size: int | None = Field(default=None)
    status: MessageStatus = Field(default=MessageStatus.sent)
    is_deleted: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
