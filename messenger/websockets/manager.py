"""Менеджер WebSocket подключений."""

from collections import defaultdict

from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    """Управление активными WebSocket подключениями.

    Хранит подключения по user_id и chat_id для эффективной рассылки.
    """

    def __init__(self) -> None:
        # user_id -> WebSocket
        self._active_connections: dict[int, WebSocket] = {}
        # chat_id -> set[user_id]
        self._chat_subscriptions: dict[int, set[int]] = defaultdict(set)
        # user_id -> set[chat_id]
        self._user_subscriptions: dict[int, set[int]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, user_id: int) -> None:
        """Принять новое WebSocket подключение."""
        await websocket.accept()
        self._active_connections[user_id] = websocket
        logger.info(f"WebSocket connected: user {user_id}")

    def disconnect(self, user_id: int) -> None:
        """Отключить пользователя."""
        self._active_connections.pop(user_id, None)

        # Удалить из всех подписок чатов
        for chat_id in list(self._user_subscriptions.get(user_id, set())):
            self._chat_subscriptions[chat_id].discard(user_id)
            if not self._chat_subscriptions[chat_id]:
                del self._chat_subscriptions[chat_id]

        self._user_subscriptions.pop(user_id, None)
        logger.info(f"WebSocket disconnected: user {user_id}")

    def subscribe(self, user_id: int, chat_id: int) -> None:
        """Подписать пользователя на чат."""
        self._chat_subscriptions[chat_id].add(user_id)
        self._user_subscriptions[user_id].add(chat_id)
        logger.debug(f"User {user_id} subscribed to chat {chat_id}")

    def unsubscribe(self, user_id: int, chat_id: int) -> None:
        """Отписать пользователя от чата."""
        self._chat_subscriptions[chat_id].discard(user_id)
        self._user_subscriptions[user_id].discard(chat_id)

        if not self._chat_subscriptions[chat_id]:
            del self._chat_subscriptions[chat_id]

        if not self._user_subscriptions[user_id]:
            del self._user_subscriptions[user_id]

        logger.debug(f"User {user_id} unsubscribed from chat {chat_id}")

    async def send_personal_message(self, user_id: int, message: dict) -> bool:
        """Отправить персональное сообщение."""
        ws = self._active_connections.get(user_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception:
            self.disconnect(user_id)
            return False

    async def broadcast_to_chat(self, chat_id: int, message: dict, exclude_user_id: int | None = None) -> int:
        """Отправить сообщение всем подписчикам чата.

        Returns:
            Количество доставленных сообщений.
        """
        subscribers = self._chat_subscriptions.get(chat_id, set()).copy()
        delivered = 0

        for user_id in subscribers:
            if user_id == exclude_user_id:
                continue

            ws = self._active_connections.get(user_id)
            if ws is None:
                continue

            try:
                await ws.send_json(message)
                delivered += 1
            except Exception:
                self.disconnect(user_id)

        return delivered

    def get_online_users(self, chat_id: int) -> set[int]:
        """Получить онлайн-пользователей в чате."""
        subscribers = self._chat_subscriptions.get(chat_id, set())
        return {uid for uid in subscribers if uid in self._active_connections}

    def is_online(self, user_id: int) -> bool:
        """Проверить онлайн ли пользователь."""
        return user_id in self._active_connections


# Глобальный экземпляр
manager = ConnectionManager()
