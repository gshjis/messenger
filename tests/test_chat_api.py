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

    async def test_create_group_chat(self, client: AsyncClient, test_session: AsyncSession):
        """Создание группового чата."""
        user = User(username="chatter", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token(data={"sub": user.id})

        response = await client.post(
            "/api/chats",
            json={"type": "group", "name": "Test Group", "member_ids": []},
            cookies={"access_token": token},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Group"
        assert data["type"] == "group"
        assert data["member_count"] == 1  # только создатель

    async def test_list_chats(self, client: AsyncClient, test_session: AsyncSession):
        """Список чатов пользователя."""
        user = User(username="lister", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        chat = Chat(type=ChatType.group, name="My Chat")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        member = ChatMember(chat_id=chat.id, user_id=user.id, role=MemberRole.admin)
        test_session.add(member)
        await test_session.commit()

        token = create_access_token(data={"sub": user.id})

        response = await client.get(
            "/api/chats",
            cookies={"access_token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "My Chat"

    async def test_get_chat_not_member(self, client: AsyncClient, test_session: AsyncSession):
        """Получение чата — пользователь не участник."""
        user = User(username="outsider", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        chat = Chat(type=ChatType.group, name="Private")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        token = create_access_token(data={"sub": user.id})

        response = await client.get(
            f"/api/chats/{chat.id}",
            cookies={"access_token": token},
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestMessageAPI:
    """Тесты API сообщений."""

    async def test_send_message(self, client: AsyncClient, test_session: AsyncSession):
        """Отправка сообщения."""
        user = User(username="sender", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        chat = Chat(type=ChatType.group, name="Chat")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        member = ChatMember(chat_id=chat.id, user_id=user.id, role=MemberRole.admin)
        test_session.add(member)
        await test_session.commit()

        token = create_access_token(data={"sub": user.id})

        response = await client.post(
            f"/api/chats/{chat.id}/messages",
            json={"content": "Hello, world!"},
            cookies={"access_token": token},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Hello, world!"
        assert data["sender_username"] == "sender"

    async def test_get_messages_paginated(self, client: AsyncClient, test_session: AsyncSession):
        """Получение сообщений с пагинацией."""
        user = User(username="paginator", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        chat = Chat(type=ChatType.group, name="Paginated Chat")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        member = ChatMember(chat_id=chat.id, user_id=user.id, role=MemberRole.admin)
        test_session.add(member)
        await test_session.commit()

        # Создание сообщений
        for i in range(5):
            msg = Message(chat_id=chat.id, sender_id=user.id, content=f"Message {i}")
            test_session.add(msg)
        await test_session.commit()

        token = create_access_token(data={"sub": user.id})

        response = await client.get(
            f"/api/chats/{chat.id}/messages?page=1&per_page=2",
            cookies={"access_token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["total"] == 5
        assert data["has_next"] is True

    async def test_search_messages(self, client: AsyncClient, test_session: AsyncSession):
        """Поиск сообщений."""
        user = User(username="searcher", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        chat = Chat(type=ChatType.group, name="Search Chat")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        member = ChatMember(chat_id=chat.id, user_id=user.id, role=MemberRole.admin)
        test_session.add(member)
        await test_session.commit()

        msg = Message(chat_id=chat.id, sender_id=user.id, content="Find this message")
        test_session.add(msg)
        msg2 = Message(chat_id=chat.id, sender_id=user.id, content="Not this one")
        test_session.add(msg2)
        await test_session.commit()

        token = create_access_token(data={"sub": user.id})

        response = await client.get(
            f"/api/chats/{chat.id}/messages/search?q=Find",
            cookies={"access_token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["messages"][0]["content"] == "Find this message"

    async def test_delete_message(self, client: AsyncClient, test_session: AsyncSession):
        """Удаление сообщения."""
        user = User(username="deleter", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        chat = Chat(type=ChatType.group, name="Delete Chat")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        member = ChatMember(chat_id=chat.id, user_id=user.id, role=MemberRole.admin)
        test_session.add(member)
        await test_session.commit()

        msg = Message(chat_id=chat.id, sender_id=user.id, content="Delete me")
        test_session.add(msg)
        await test_session.commit()
        await test_session.refresh(msg)

        token = create_access_token(data={"sub": user.id})

        response = await client.delete(
            f"/api/chats/{chat.id}/messages/{msg.id}",
            cookies={"access_token": token},
        )

        assert response.status_code == 204

        # Проверка что сообщение помечено удалённым
        await test_session.refresh(msg)
        assert msg.is_deleted is True