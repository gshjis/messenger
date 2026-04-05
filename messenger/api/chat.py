"""Роутеры для управления чатами."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.api.auth import get_current_user
from messenger.config import settings
from messenger.database import get_session
from messenger.models.chat import Chat, ChatType
from messenger.models.chat_member import ChatMember, MemberRole
from messenger.models.message import Message, MessageStatus
from messenger.models.user import User
from messenger.schemas.chat import (
    AddMemberRequest,
    ChatCreate,
    ChatMemberResponse,
    ChatResponse,
    CreatePersonalChatRequest,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    SearchMessagesResponse,
    UpdateMemberRoleRequest,
)

router = APIRouter(prefix="/api/chats", tags=["chats"])


# ============================================
# Helpers
# ============================================

async def check_chat_member(
    chat_id: int,
    user_id: int,
    session: AsyncSession,
) -> ChatMember | None:
    """Проверка что пользователь — участник чата."""
    result = await session.exec(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == user_id,
        )
    )
    member = result.first()
    return member


async def check_chat_admin(
    chat_id: int,
    user_id: int,
    session: AsyncSession,
) -> bool:
    """Проверка что пользователь — админ чата."""
    result = await session.exec(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == user_id,
            ChatMember.role == MemberRole.admin,
        )
    )
    return result.first() is not None


# ============================================
# CRUD чатов
# ============================================

@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    data: ChatCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    """Создание чата (личный или групповой)."""
    chat = Chat(type=data.type, name=data.name, description=data.description)
    session.add(chat)
    await session.flush()

    # Создатель — админ
    admin_member = ChatMember(chat_id=chat.id, user_id=current_user.id, role=MemberRole.admin)
    session.add(admin_member)

    # Добавление указанных участников
    for member_id in data.member_ids:
        if member_id == current_user.id:
            continue
        result = await session.exec(select(User).where(User.id == member_id))
        user = result.first()
        if user is None:
            raise HTTPException(status_code=400, detail=f"User {member_id} not found")

        member = ChatMember(chat_id=chat.id, user_id=member_id, role=MemberRole.member)
        session.add(member)

    await session.commit()
    await session.refresh(chat)

    # Подсчёт участников
    count_result = await session.exec(
        select(func.count()).select_from(ChatMember).where(ChatMember.chat_id == chat.id)
    )
    member_count = count_result.one()

    return ChatResponse(
        id=chat.id,
        type=chat.type,
        name=chat.name,
        description=chat.description,
        avatar_path=chat.avatar_path,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        member_count=member_count,
    )


@router.post("/personal", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_or_get_personal_chat(
    data: CreatePersonalChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    """Создание или получение личного чата с другим пользователем.
    
    Если personal чат между двумя пользователями уже существует — возвращает его.
    Иначе создаёт новый чат с обоими участниками.
    """
    assert current_user.id is not None
    
    # Проверка что пользователь не пытается создать чат с собой
    if data.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot create chat with yourself")
    
    # Проверка что второй пользователь существует
    result = await session.exec(select(User).where(User.id == data.user_id))
    other_user = result.first()
    if other_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Поиск существующего personal чата между пользователями
    existing_result = await session.exec(
        select(Chat)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .where(
            Chat.type == ChatType.personal,
            ChatMember.user_id == current_user.id,
        )
    )
    existing_chats = existing_result.all()
    
    for chat in existing_chats:
        # Проверяем есть ли второй пользователь в этом чате
        members_result = await session.exec(
            select(ChatMember).where(
                ChatMember.chat_id == chat.id,
                ChatMember.user_id == data.user_id,
            )
        )
        if members_result.first() is not None:
            # Чат уже существует — возвращаем его
            count_result = await session.exec(
                select(func.count()).select_from(ChatMember).where(ChatMember.chat_id == chat.id)
            )
            return ChatResponse(
                id=chat.id,  # type: ignore[arg-type]
                type=chat.type,
                name=chat.name,
                description=chat.description,
                avatar_path=chat.avatar_path,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
                member_count=count_result.one(),
            )
    
    # Создаём новый personal чат
    chat = Chat(type=ChatType.personal, name=None, description=None)
    session.add(chat)
    await session.flush()
    
    # Добавляем обоих участников как admin
    member1 = ChatMember(chat_id=chat.id, user_id=current_user.id, role=MemberRole.admin)  # type: ignore[arg-type]
    member2 = ChatMember(chat_id=chat.id, user_id=data.user_id, role=MemberRole.admin)  # type: ignore[arg-type]
    session.add(member1)
    session.add(member2)
    
    await session.commit()
    await session.refresh(chat)
    
    return ChatResponse(
        id=chat.id,  # type: ignore[arg-type]
        type=chat.type,
        name=chat.name,
        description=chat.description,
        avatar_path=chat.avatar_path,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        member_count=2,
    )


@router.get("", response_model=list[ChatResponse])
async def list_chats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ChatResponse]:
    """Список чатов пользователя."""
    result = await session.exec(
        select(Chat)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .where(ChatMember.user_id == current_user.id)
        .order_by(col(Chat.updated_at).desc())
    )
    chats = result.all()

    response = []
    for chat in chats:
        count_result = await session.exec(
            select(func.count()).select_from(ChatMember).where(ChatMember.chat_id == chat.id)
        )
        response.append(
            ChatResponse(
                id=chat.id,
                type=chat.type,
                name=chat.name,
                description=chat.description,
                avatar_path=chat.avatar_path,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
                member_count=count_result.one(),
            )
        )

    return response


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    """Информация о чате."""
    assert current_user.id is not None
    membership = await check_chat_member(chat_id, current_user.id, session)
    if membership is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    result = await session.exec(select(Chat).where(Chat.id == chat_id))
    chat = result.first()
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    count_result = await session.exec(
        select(func.count()).select_from(ChatMember).where(ChatMember.chat_id == chat.id)
    )

    return ChatResponse(
        id=chat.id,
        type=chat.type,
        name=chat.name,
        description=chat.description,
        avatar_path=chat.avatar_path,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        member_count=count_result.one(),
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Удаление чата (только админ)."""
    assert current_user.id is not None
    is_admin = await check_chat_admin(chat_id, current_user.id, session)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only chat admin can delete")

    result = await session.exec(select(Chat).where(Chat.id == chat_id))
    chat = result.first()
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Удаление сообщений и участников
    messages_result = await session.exec(
        select(Message).where(Message.chat_id == chat_id)
    )
    for msg in messages_result.all():
        await session.delete(msg)

    members_result = await session.exec(
        select(ChatMember).where(ChatMember.chat_id == chat_id)
    )
    for member in members_result.all():
        await session.delete(member)

    await session.delete(chat)
    await session.commit()

    logger.info(f"Chat {chat_id} deleted by user {current_user.id}")


# ============================================
# Управление участниками
# ============================================

@router.get("/{chat_id}/members", response_model=list[ChatMemberResponse])
async def list_members(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ChatMemberResponse]:
    """Список участников чата."""
    assert current_user.id is not None
    membership = await check_chat_member(chat_id, current_user.id, session)
    if membership is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    result = await session.exec(
        select(ChatMember, User.username)
        .join(User, User.id == ChatMember.user_id)
        .where(ChatMember.chat_id == chat_id)
    )
    rows = result.all()

    return [
        ChatMemberResponse(
            id=cm.id,
            user_id=cm.user_id,
            username=username,
            role=cm.role,
            joined_at=cm.joined_at,
        )
        for cm, username in rows
    ]


@router.post("/{chat_id}/members", response_model=ChatMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    chat_id: int,
    data: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatMemberResponse:
    """Добавление участника (только админ)."""
    assert current_user.id is not None
    is_admin = await check_chat_admin(chat_id, current_user.id, session)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only chat admin can add members")

    # Проверка что пользователь существует
    result = await session.exec(select(User).where(User.id == data.user_id))
    user = result.first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверка что уже не участник
    existing = await check_chat_member(chat_id, data.user_id, session)
    if existing is not None:
        raise HTTPException(status_code=400, detail="User is already a member")

    member = ChatMember(chat_id=chat_id, user_id=data.user_id, role=data.role)
    session.add(member)
    await session.commit()
    await session.refresh(member)

    logger.info(f"User {data.user_id} added to chat {chat_id}")
    return ChatMemberResponse(
        id=member.id,
        user_id=member.user_id,
        username=user.username,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete("/{chat_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    chat_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Удаление участника (админ или сам себя)."""
    assert current_user.id is not None
    is_admin = await check_chat_admin(chat_id, current_user.id, session)
    if not is_admin and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    membership = await check_chat_member(chat_id, user_id, session)
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    await session.delete(membership)
    await session.commit()

    logger.info(f"User {user_id} removed from chat {chat_id}")


@router.put("/{chat_id}/members/{user_id}/role", response_model=ChatMemberResponse)
async def update_member_role(
    chat_id: int,
    user_id: int,
    data: UpdateMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatMemberResponse:
    """Смена роли участника (только админ)."""
    assert current_user.id is not None
    is_admin = await check_chat_admin(chat_id, current_user.id, session)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only chat admin can change roles")

    membership = await check_chat_member(chat_id, user_id, session)
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    membership.role = data.role
    await session.commit()
    await session.refresh(membership)

    result = await session.exec(select(User.username).where(User.id == user_id))
    username = result.first()

    return ChatMemberResponse(
        id=membership.id,
        user_id=membership.user_id,
        username=username or "",
        role=membership.role,
        joined_at=membership.joined_at,
    )


# ============================================
# Сообщения
# ============================================

@router.post("/{chat_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    chat_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """Отправка сообщения."""
    assert current_user.id is not None
    membership = await check_chat_member(chat_id, current_user.id, session)
    if membership is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    if not data.content:
        raise HTTPException(status_code=400, detail="Message content is required")

    message = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        content=data.content,
    )
    session.add(message)

    # Обновление updated_at чата
    result = await session.exec(select(Chat).where(Chat.id == chat_id))
    chat = result.first()
    if chat:
        from datetime import datetime, timezone
        chat.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(message)

    return MessageResponse(
        id=message.id,
        chat_id=message.chat_id,
        sender_id=message.sender_id,
        sender_username=current_user.username,
        content=message.content,
        file_path=message.file_path,
        file_mime=message.file_mime,
        file_size=message.file_size,
        status=message.status,
        created_at=message.created_at,
    )


@router.get("/{chat_id}/messages", response_model=MessageListResponse)
async def get_messages(
    chat_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MessageListResponse:
    """Получение сообщений с пагинацией."""
    assert current_user.id is not None
    membership = await check_chat_member(chat_id, current_user.id, session)
    if membership is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Общее количество
    count_result = await session.exec(
        select(func.count()).select_from(Message).where(
            Message.chat_id == chat_id,
            Message.is_deleted == False,  # noqa: E712
        )
    )
    total = count_result.one()

    # Сообщения
    offset = (page - 1) * per_page
    result = await session.exec(
        select(Message, User.username)
        .join(User, User.id == Message.sender_id)
        .where(
            Message.chat_id == chat_id,
            Message.is_deleted == False,  # noqa: E712
        )
        .order_by(col(Message.created_at).desc())
        .offset(offset)
        .limit(per_page)
    )
    rows = result.all()

    messages = [
        MessageResponse(
            id=msg.id,
            chat_id=msg.chat_id,
            sender_id=msg.sender_id,
            sender_username=username,
            content=msg.content,
            file_path=msg.file_path,
            file_mime=msg.file_mime,
            file_size=msg.file_size,
            status=msg.status,
            created_at=msg.created_at,
        )
        for msg, username in rows
    ]

    return MessageListResponse(
        messages=messages,
        total=total,
        page=page,
        per_page=per_page,
        has_next=(page * per_page) < total,
    )


@router.get("/{chat_id}/messages/search", response_model=SearchMessagesResponse)
async def search_messages(
    chat_id: int,
    q: str = Query(min_length=1, max_length=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SearchMessagesResponse:
    """Поиск по тексту сообщений."""
    assert current_user.id is not None
    membership = await check_chat_member(chat_id, current_user.id, session)
    if membership is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Экранирование спецсимволов LIKE
    escaped_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    # Общее количество
    count_result = await session.exec(
        select(func.count()).select_from(Message).where(
            Message.chat_id == chat_id,
            Message.is_deleted == False,  # noqa: E712
            Message.content.like(f"%{escaped_q}%"),
        )
    )
    total = count_result.one()

    # Сообщения
    result = await session.exec(
        select(Message, User.username)
        .join(User, User.id == Message.sender_id)
        .where(
            Message.chat_id == chat_id,
            Message.is_deleted == False,  # noqa: E712
            Message.content.like(f"%{escaped_q}%"),
        )
        .order_by(col(Message.created_at).desc())
        .limit(50)
    )
    rows = result.all()

    messages = [
        MessageResponse(
            id=msg.id,
            chat_id=msg.chat_id,
            sender_id=msg.sender_id,
            sender_username=username,
            content=msg.content,
            file_path=msg.file_path,
            file_mime=msg.file_mime,
            file_size=msg.file_size,
            status=msg.status,
            created_at=msg.created_at,
        )
        for msg, username in rows
    ]

    return SearchMessagesResponse(messages=messages, total=total, query=q)


@router.delete("/{chat_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    chat_id: int,
    message_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Удаление сообщения (автор или админ)."""
    assert current_user.id is not None
    result = await session.exec(
        select(Message).where(Message.id == message_id, Message.chat_id == chat_id)
    )
    message = result.first()
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")

    is_admin = await check_chat_admin(chat_id, current_user.id, session)
    if message.sender_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Not allowed")

    message.is_deleted = True
    await session.commit()

    logger.info(f"Message {message_id} deleted by user {current_user.id}")
