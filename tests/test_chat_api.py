"""Integration тесты для API чатов."""

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.models.chat import Chat, ChatType
from messenger.models.chat_member import ChatMember, MemberRole
from messenger.models.message import Message, MessageStatus
from messenger.models.user import User
from messenger.security.auth import create_access_token, hash_password


@pytest.mark.asyncio
class TestChatAPI:
    """Тесты API чатов."""

    async def test_create_group_chat(self, auth_client: AsyncClient) -> None:
        """Создание группового чата."""
        response = await auth_client.post(
            "/api/chats",
            json={"type": "group", "name": "Test Group", "member_ids": []},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Group"
        assert data["type"] == "group"
        assert data["member_count"] == 1

    async def test_list_chats(self, auth_client: AsyncClient, test_session: AsyncSession, test_user: User) -> None:
        """Список чатов пользователя."""
        assert test_user.id is not None
        chat = Chat(type=ChatType.group, name="My Chat")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)
        assert chat.id is not None

        member = ChatMember(chat_id=chat.id, user_id=test_user.id, role=MemberRole.admin)
        test_session.add(member)
        await test_session.commit()

        response = await auth_client.get("/api/chats")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "My Chat"

    async def test_get_chat_not_member(self, auth_client: AsyncClient, test_session: AsyncSession, test_user: User) -> None:
        """Получение чата — пользователь не участник."""
        assert test_user.id is not None
        chat = Chat(type=ChatType.group, name="Private")
        test_session.add(chat)
        await test_session.commit()

        response = await auth_client.get(f"/api/chats/{chat.id}")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestMessageAPI:
    """Тесты API сообщений."""

    async def test_send_message(self, auth_client: AsyncClient, test_session: AsyncSession, test_user: User) -> None:
        """Отправка сообщения."""
        assert test_user.id is not None
        chat = Chat(type=ChatType.group, name="Chat")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)
        assert chat.id is not None

        member = ChatMember(chat_id=chat.id, user_id=test_user.id, role=MemberRole.admin)
        test_session.add(member)
        await test_session.commit()

        response = await auth_client.post(
            f"/api/chats/{chat.id}/messages",
            json={"content": "Hello, world!"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Hello, world!"
        assert data["sender_username"] == test_user.username

    async def test_get_messages_paginated(self, auth_client: AsyncClient, test_session: AsyncSession, test_user: User) -> None:
        """Получение сообщений с пагинацией."""
        assert test_user.id is not None
        chat = Chat(type=ChatType.group, name="Paginated Chat")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)
        assert chat.id is not None

        member = ChatMember(chat_id=chat.id, user_id=test_user.id, role=MemberRole.admin)
        test_session.add(member)
        await test_session.commit()

        for i in range(5):
            msg = Message(chat_id=chat.id, sender_id=test_user.id, content=f"Message {i}")
            test_session.add(msg)
        await test_session.commit()

        response = await auth_client.get(f"/api/chats/{chat.id}/messages?page=1&per_page=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["total"] == 5
        assert data["has_next"] is True

    async def test_search_messages(self, auth_client: AsyncClient, test_session: AsyncSession, test_user: User) -> None:
        """Поиск сообщений."""
        assert test_user.id is not None
        chat = Chat(type=ChatType.group, name="Search Chat")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)
        assert chat.id is not None

        member = ChatMember(chat_id=chat.id, user_id=test_user.id, role=MemberRole.admin)
        test_session.add(member)
        await test_session.commit()

        msg = Message(chat_id=chat.id, sender_id=test_user.id, content="Find this message")
        test_session.add(msg)
        msg2 = Message(chat_id=chat.id, sender_id=test_user.id, content="Not this one")
        test_session.add(msg2)
        await test_session.commit()

        response = await auth_client.get(f"/api/chats/{chat.id}/messages/search?q=Find")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["messages"][0]["content"] == "Find this message"

    async def test_delete_message(self, auth_client: AsyncClient, test_session: AsyncSession, test_user: User) -> None:
        """Удаление сообщения."""
        assert test_user.id is not None
        chat = Chat(type=ChatType.group, name="Delete Chat")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)
        assert chat.id is not None

        member = ChatMember(chat_id=chat.id, user_id=test_user.id, role=MemberRole.admin)
        test_session.add(member)
        await test_session.commit()

        msg = Message(chat_id=chat.id, sender_id=test_user.id, content="Delete me")
        test_session.add(msg)
        await test_session.commit()
        await test_session.refresh(msg)

        response = await auth_client.delete(f"/api/chats/{chat.id}/messages/{msg.id}")
        assert response.status_code == 204

        await test_session.refresh(msg)
        assert msg.is_deleted is True


@pytest.mark.asyncio
class TestPersonalChatAPI:
    """Тесты личных чатов."""

    async def test_create_personal_chat(self, auth_client: AsyncClient, test_session: AsyncSession, test_user: User) -> None:
        """Создание личного чата."""
        assert test_user.id is not None
        other_user = User(username="other_user", hashed_password=hash_password("SecurePass123!"))
        test_session.add(other_user)
        await test_session.commit()
        await test_session.refresh(other_user)

        response = await auth_client.post(
            "/api/chats/personal",
            json={"user_id": other_user.id},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "personal"
        assert data["member_count"] == 2

    async def test_get_existing_personal_chat(self, auth_client: AsyncClient, test_session: AsyncSession, test_user: User) -> None:
        """Получение существующего личного чата (не создаёт дубликат)."""
        assert test_user.id is not None
        other_user = User(username="other_user2", hashed_password=hash_password("SecurePass123!"))
        test_session.add(other_user)
        await test_session.commit()
        await test_session.refresh(other_user)

        # Первый запрос — создание
        response1 = await auth_client.post(
            "/api/chats/personal",
            json={"user_id": other_user.id},
        )
        assert response1.status_code == 201
        chat_id_1 = response1.json()["id"]

        # Второй запрос — должен вернуть тот же чат
        response2 = await auth_client.post(
            "/api/chats/personal",
            json={"user_id": other_user.id},
        )
        assert response2.status_code in (200, 201)
        chat_id_2 = response2.json()["id"]
        assert chat_id_1 == chat_id_2

    async def test_create_personal_chat_with_self(self, auth_client: AsyncClient, test_user: User) -> None:
        """Попытка создать чат с собой."""
        assert test_user.id is not None
        response = await auth_client.post(
            "/api/chats/personal",
            json={"user_id": test_user.id},
        )
        assert response.status_code == 400

    async def test_create_personal_chat_user_not_found(self, auth_client: AsyncClient) -> None:
        """Попытка создать чат с несуществующим пользователем."""
        response = await auth_client.post(
            "/api/chats/personal",
            json={"user_id": 99999},
        )
        assert response.status_code == 404
