"""Тесты для моделей данных."""

import pytest
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.models.chat import Chat, ChatType
from messenger.models.chat_member import ChatMember, MemberRole
from messenger.models.invite_code import InviteCode
from messenger.models.message import Message, MessageStatus
from messenger.models.user import User


@pytest.mark.asyncio
class TestUserModel:
    """Тесты модели User."""

    async def test_create_user(self, test_session: AsyncSession):
        """Создание пользователя."""
        user = User(username="testuser", hashed_password="hashed_pass")
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        assert user.id is not None
        assert user.username == "testuser"
        assert user.is_active is True
        assert user.is_banned is False
        assert user.avatar_path is None

    async def test_user_unique_username(self, test_session: AsyncSession):
        """Username должен быть уникальным."""
        user1 = User(username="unique_user", hashed_password="hashed_pass")
        test_session.add(user1)
        await test_session.commit()

        user2 = User(username="unique_user", hashed_password="hashed_pass2")
        test_session.add(user2)

        with pytest.raises(Exception):
            await test_session.commit()

    async def test_user_defaults(self, test_session: AsyncSession):
        """Проверка значений по умолчанию."""
        user = User(username="defaults_test", hashed_password="hashed_pass")
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        assert user.is_active is True
        assert user.is_banned is False
        assert user.created_at is not None
        assert user.updated_at is not None

    # SQLModel не валидирует max_length на уровне Python — только в БД
    # Тест на уровне БД требует отдельной проверки constraints


@pytest.mark.asyncio
class TestChatModel:
    """Тесты модели Chat."""

    async def test_create_personal_chat(self, test_session: AsyncSession):
        """Создание личного чата."""
        chat = Chat(type=ChatType.personal)
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        assert chat.id is not None
        assert chat.type == ChatType.personal
        assert chat.name is None

    async def test_create_group_chat(self, test_session: AsyncSession):
        """Создание группового чата."""
        chat = Chat(type=ChatType.group, name="Test Group")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        assert chat.type == ChatType.group
        assert chat.name == "Test Group"

    # SQLModel не валидирует max_length на уровне Python — только в БД


@pytest.mark.asyncio
class TestChatMemberModel:
    """Тесты модели ChatMember."""

    async def test_create_chat_member(self, test_session: AsyncSession):
        """Создание участника чата."""
        user = User(username="member_test", hashed_password="hashed_pass")
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        chat = Chat(type=ChatType.group, name="Test")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        member = ChatMember(chat_id=chat.id, user_id=user.id, role=MemberRole.admin)
        test_session.add(member)
        await test_session.commit()
        await test_session.refresh(member)

        assert member.id is not None
        assert member.role == MemberRole.admin
        assert member.joined_at is not None

    async def test_chat_member_default_role(self, test_session: AsyncSession):
        """Роль по умолчанию — member."""
        user = User(username="role_test", hashed_password="hashed_pass")
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        chat = Chat(type=ChatType.group, name="Test")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        member = ChatMember(chat_id=chat.id, user_id=user.id)
        test_session.add(member)
        await test_session.commit()
        await test_session.refresh(member)

        assert member.role == MemberRole.member


@pytest.mark.asyncio
class TestMessageModel:
    """Тесты модели Message."""

    async def test_create_message(self, test_session: AsyncSession):
        """Создание сообщения."""
        user = User(username="msg_sender", hashed_password="hashed_pass")
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        chat = Chat(type=ChatType.group, name="Test")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        msg = Message(
            chat_id=chat.id,
            sender_id=user.id,
            content="Hello, world!",
        )
        test_session.add(msg)
        await test_session.commit()
        await test_session.refresh(msg)

        assert msg.id is not None
        assert msg.content == "Hello, world!"
        assert msg.status == MessageStatus.sent
        assert msg.is_deleted is False

    async def test_message_with_file(self, test_session: AsyncSession):
        """Сообщение с файлом."""
        user = User(username="file_sender", hashed_password="hashed_pass")
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        chat = Chat(type=ChatType.group, name="Test")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        msg = Message(
            chat_id=chat.id,
            sender_id=user.id,
            content="Check this file",
            file_path="/uploads/test.jpg",
            file_mime="image/jpeg",
            file_size=102400,
        )
        test_session.add(msg)
        await test_session.commit()
        await test_session.refresh(msg)

        assert msg.file_path == "/uploads/test.jpg"
        assert msg.file_mime == "image/jpeg"
        assert msg.file_size == 102400

    async def test_message_status_update(self, test_session: AsyncSession):
        """Обновление статуса сообщения."""
        user = User(username="status_user", hashed_password="hashed_pass")
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        chat = Chat(type=ChatType.group, name="Test")
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        msg = Message(chat_id=chat.id, sender_id=user.id, content="Test")
        test_session.add(msg)
        await test_session.commit()
        await test_session.refresh(msg)

        assert msg.status == MessageStatus.sent

        msg.status = MessageStatus.delivered
        await test_session.commit()
        await test_session.refresh(msg)
        assert msg.status == MessageStatus.delivered

        msg.status = MessageStatus.read
        await test_session.commit()
        await test_session.refresh(msg)
        assert msg.status == MessageStatus.read


@pytest.mark.asyncio
class TestInviteCodeModel:
    """Тесты модели InviteCode."""

    async def test_create_invite_code(self, test_session: AsyncSession):
        """Создание invite-кода."""
        code = InviteCode(code="TEST1234")
        test_session.add(code)
        await test_session.commit()
        await test_session.refresh(code)

        assert code.id is not None
        assert code.code == "TEST1234"
        assert code.max_uses == 1
        assert code.used_count == 0
        assert code.is_active is True

    async def test_invite_code_unique(self, test_session: AsyncSession):
        """Invite-код должен быть уникальным."""
        code1 = InviteCode(code="UNIQUE1")
        test_session.add(code1)
        await test_session.commit()

        code2 = InviteCode(code="UNIQUE1")
        test_session.add(code2)

        with pytest.raises(Exception):
            await test_session.commit()

    async def test_invite_code_custom_max_uses(self, test_session: AsyncSession):
        """Кастомное максимальное количество использований."""
        code = InviteCode(code="MULTI5", max_uses=5)
        test_session.add(code)
        await test_session.commit()
        await test_session.refresh(code)

        assert code.max_uses == 5

    async def test_invite_code_increment_uses(self, test_session: AsyncSession):
        """Увеличение счётчика использований."""
        code = InviteCode(code="USEME1")
        test_session.add(code)
        await test_session.commit()
        await test_session.refresh(code)

        assert code.used_count == 0

        code.used_count += 1
        await test_session.commit()
        await test_session.refresh(code)

        assert code.used_count == 1