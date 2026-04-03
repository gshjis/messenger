"""Pydantic схемы для чатов и сообщений."""

from datetime import datetime

from pydantic import BaseModel, Field

from messenger.models.chat import ChatType
from messenger.models.chat_member import MemberRole
from messenger.models.message import MessageStatus


class ChatCreate(BaseModel):
    """Создание чата."""

    type: ChatType = ChatType.group
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    member_ids: list[int] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Ответ с данными чата."""

    id: int
    type: ChatType
    name: str | None
    description: str | None
    avatar_path: str | None
    created_at: datetime
    updated_at: datetime
    member_count: int = 0

    model_config = {"from_attributes": True}


class ChatMemberResponse(BaseModel):
    """Ответ с данными участника чата."""

    id: int
    user_id: int
    username: str
    role: MemberRole
    joined_at: datetime

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    """Добавление участника."""

    user_id: int
    role: MemberRole = MemberRole.member


class UpdateMemberRoleRequest(BaseModel):
    """Смена роли участника."""

    role: MemberRole


class MessageCreate(BaseModel):
    """Создание сообщения."""

    content: str | None = Field(default=None, max_length=10000)


class MessageResponse(BaseModel):
    """Ответ с данными сообщения."""

    id: int
    chat_id: int
    sender_id: int
    sender_username: str
    content: str | None
    file_path: str | None
    file_mime: str | None
    file_size: int | None
    status: MessageStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    """Список сообщений с пагинацией."""

    messages: list[MessageResponse]
    total: int
    page: int
    per_page: int
    has_next: bool


class SearchMessagesResponse(BaseModel):
    """Результат поиска сообщений."""

    messages: list[MessageResponse]
    total: int
    query: str
