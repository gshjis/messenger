"""WebSocket endpoint для real-time коммуникации."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.database import get_session
from messenger.models.chat_member import ChatMember
from messenger.models.message import Message, MessageStatus
from messenger.models.user import User
from messenger.security.auth import decode_access_token
from messenger.websockets.manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint для real-time коммуникации.

    Протокол:
    1. Подключение с token query параметром: /ws?token=xxx
    2. Аутентификация через token
    3. Подписка на чат: {"action": "subscribe", "chat_id": 1}
    4. Отписка от чата: {"action": "unsubscribe", "chat_id": 1}
    5. Отправка сообщения: {"action": "message", "chat_id": 1, "content": "Hello"}
    6. Обновление статуса: {"action": "mark_read", "chat_id": 1, "message_id": 5}
    7. Ping: {"action": "ping"} -> {"type": "pong"}
    """
    # Аутентификация
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4002, reason="Invalid token")
        return

    user_id: int | None = payload.get("sub")
    if user_id is None:
        await websocket.close(code=4003, reason="Invalid payload")
        return

    # Подключение
    await manager.connect(websocket, user_id)

    try:
        while True:
            # Получение данных
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            action = data.get("action")

            if action == "subscribe":
                await handle_subscribe(data, user_id, websocket)

            elif action == "unsubscribe":
                await handle_unsubscribe(data, user_id)

            elif action == "message":
                await handle_message(data, user_id)

            elif action == "mark_read":
                await handle_mark_read(data, user_id)

            elif action == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({"type": "error", "message": f"Unknown action: {action}"})

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(user_id)


async def handle_subscribe(data: dict, user_id: int, websocket: WebSocket) -> None:
    """Подписка на чат."""
    chat_id = data.get("chat_id")
    if chat_id is None:
        await websocket.send_json({"type": "error", "message": "chat_id required"})
        return

    manager.subscribe(user_id, chat_id)
    await websocket.send_json({"type": "subscribed", "chat_id": chat_id})


async def handle_unsubscribe(data: dict, user_id: int) -> None:
    """Отписка от чата."""
    chat_id = data.get("chat_id")
    if chat_id is None:
        return

    manager.unsubscribe(user_id, chat_id)


async def handle_message(data: dict, user_id: int) -> None:
    """Отправка сообщения в чат."""
    chat_id = data.get("chat_id")
    content = data.get("content")

    if chat_id is None or content is None:
        return

    # Проверка что пользователь подписан на чат
    if user_id not in manager._chat_subscriptions.get(chat_id, set()):
        return

    # Сохранение в БД
    async for session in get_session():
        # Проверка участника
        result = await session.exec(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id,
                ChatMember.user_id == user_id,
            )
        )
        if result.first() is None:
            return

        # Получение username
        user_result = await session.exec(select(User).where(User.id == user_id))
        user = user_result.first()
        username = user.username if user else "unknown"

        # Создание сообщения
        message = Message(
            chat_id=chat_id,
            sender_id=user_id,
            content=content,
        )
        session.add(message)

        # Обновление updated_at чата
        from datetime import datetime, timezone
        from messenger.models.chat import Chat

        chat_result = await session.exec(select(Chat).where(Chat.id == chat_id))
        chat = chat_result.first()
        if chat:
            chat.updated_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(message)

        # Отправка всем подписчикам
        broadcast_data = {
            "type": "new_message",
            "chat_id": chat_id,
            "message": {
                "id": message.id,
                "chat_id": message.chat_id,
                "sender_id": message.sender_id,
                "sender_username": username,
                "content": message.content,
                "file_path": message.file_path,
                "file_mime": message.file_mime,
                "file_size": message.file_size,
                "status": message.status,
                "created_at": message.created_at.isoformat(),
            },
        }

        await manager.broadcast_to_chat(chat_id, broadcast_data, exclude_user_id=user_id)
        break


async def handle_mark_read(data: dict, user_id: int) -> None:
    """Обновление статуса сообщений на 'прочитано'."""
    chat_id = data.get("chat_id")
    message_id = data.get("message_id")

    if chat_id is None:
        return

    async for session in get_session():
        if message_id:
            # Конкретное сообщение
            result = await session.exec(
                select(Message).where(
                    Message.id == message_id,
                    Message.chat_id == chat_id,
                )
            )
            message = result.first()
            if message:
                message.status = MessageStatus.read
                await session.commit()

                # Уведомление отправителю
                await manager.send_personal_message(
                    message.sender_id,
                    {
                        "type": "message_read",
                        "chat_id": chat_id,
                        "message_id": message.id,
                        "read_by": user_id,
                    },
                )
        else:
            # Все сообщения в чате от других пользователей
            result = await session.exec(
                select(Message).where(
                    Message.chat_id == chat_id,
                    Message.sender_id != user_id,
                    Message.status != MessageStatus.read,
                )
            )
            messages = result.all()
            for msg in messages:
                msg.status = MessageStatus.read

                # Уведомление отправителю
                await manager.send_personal_message(
                    msg.sender_id,
                    {
                        "type": "message_read",
                        "chat_id": chat_id,
                        "message_id": msg.id,
                        "read_by": user_id,
                    },
                )

            await session.commit()
        break
