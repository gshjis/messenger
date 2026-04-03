"""Тесты для аутентификации."""

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.models.invite_code import InviteCode
from messenger.security.auth import hash_password


@pytest.mark.asyncio
class TestAuthLogin:
    """Тесты логина."""

    async def test_login_success(self, client: AsyncClient, test_session: AsyncSession):
        """Успешный логин."""
        from messenger.models.user import User

        user = User(username="logintest", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()

        response = await client.post(
            "/api/auth/login",
            json={"username": "logintest", "password": "SecurePass123!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_session: AsyncSession):
        """Неверный пароль."""
        from messenger.models.user import User

        user = User(username="wrongpass", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()

        response = await client.post(
            "/api/auth/login",
            json={"username": "wrongpass", "password": "WrongPassword"},
        )

        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Несуществующий пользователь."""
        response = await client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "SecurePass123!"},
        )

        assert response.status_code == 401

    async def test_login_banned_user(self, client: AsyncClient, test_session: AsyncSession):
        """Забаненный пользователь."""
        from messenger.models.user import User

        user = User(username="banned", hashed_password=hash_password("SecurePass123!"), is_banned=True)
        test_session.add(user)
        await test_session.commit()

        response = await client.post(
            "/api/auth/login",
            json={"username": "banned", "password": "SecurePass123!"},
        )

        assert response.status_code == 403


@pytest.mark.asyncio
class TestAuthRegister:
    """Тесты регистрации."""

    async def test_register_success(self, client: AsyncClient, test_session: AsyncSession):
        """Успешная регистрация."""
        invite = InviteCode(code="REGTEST1")
        test_session.add(invite)
        await test_session.commit()

        response = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "password": "SecurePass123!",
                "invite_code": "REGTEST1",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data

        # Проверка что invite использован
        from sqlmodel import select

        result = await test_session.exec(select(InviteCode).where(InviteCode.code == "REGTEST1"))
        used_invite = result.first()
        assert used_invite is not None
        assert used_invite.used_count == 1
        assert used_invite.is_active is False

    async def test_register_invalid_invite(self, client: AsyncClient):
        """Регистрация с несуществующим invite-кодом."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "password": "SecurePass123!",
                "invite_code": "INVALID",
            },
        )

        assert response.status_code == 400

    async def test_register_duplicate_username(self, client: AsyncClient, test_session: AsyncSession):
        """Регистрация с занятым username."""
        from messenger.models.user import User

        user = User(username="taken", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()

        invite = InviteCode(code="DUPTEST1")
        test_session.add(invite)
        await test_session.commit()

        response = await client.post(
            "/api/auth/register",
            json={
                "username": "taken",
                "password": "SecurePass123!",
                "invite_code": "DUPTEST1",
            },
        )

        assert response.status_code == 400

    async def test_register_used_invite(self, client: AsyncClient, test_session: AsyncSession):
        """Регистрация с использованным invite-кодом."""
        invite = InviteCode(code="USEDTEST", used_count=1, max_uses=1, is_active=False)
        test_session.add(invite)
        await test_session.commit()

        response = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser2",
                "password": "SecurePass123!",
                "invite_code": "USEDTEST",
            },
        )

        assert response.status_code == 400


@pytest.mark.asyncio
class TestAuthMe:
    """Тесты получения текущего пользователя."""

    async def test_get_me_authenticated(self, client: AsyncClient, test_session: AsyncSession):
        """Получение данных авторизованного пользователя."""
        from messenger.models.user import User
        from messenger.security.auth import create_access_token

        user = User(username="metest", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token(data={"sub": user.id})

        response = await client.get(
            "/api/auth/me",
            cookies={"access_token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "metest"
        assert data["id"] == user.id

    async def test_get_me_no_token(self, client: AsyncClient):
        """Получение данных без токена."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_get_me_invalid_token(self, client: AsyncClient):
        """Получение данных с невалидным токеном."""
        response = await client.get(
            "/api/auth/me",
            cookies={"access_token": "invalid.token.here"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestAuthProfile:
    """Тесты обновления профиля."""

    async def test_update_username(self, client: AsyncClient, test_session: AsyncSession):
        """Смена username."""
        from messenger.models.user import User
        from messenger.security.auth import create_access_token

        user = User(username="oldname", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token(data={"sub": user.id})

        response = await client.put(
            "/api/auth/me",
            json={"username": "newname"},
            cookies={"access_token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newname"

    async def test_update_duplicate_username(self, client: AsyncClient, test_session: AsyncSession):
        """Смена username на занятый."""
        from messenger.models.user import User
        from messenger.security.auth import create_access_token

        user1 = User(username="user1", hashed_password=hash_password("SecurePass123!"))
        user2 = User(username="user2", hashed_password=hash_password("SecurePass123!"))
        test_session.add_all([user1, user2])
        await test_session.commit()
        await test_session.refresh(user1)

        token = create_access_token(data={"sub": user1.id})

        response = await client.put(
            "/api/auth/me",
            json={"username": "user2"},
            cookies={"access_token": token},
        )

        assert response.status_code == 400


@pytest.mark.asyncio
class TestAuthInvite:
    """Тесты генерации invite-кодов."""

    async def test_generate_invite(self, client: AsyncClient, test_session: AsyncSession):
        """Генерация invite-кода."""
        from messenger.models.user import User
        from messenger.security.auth import create_access_token

        user = User(username="inviter", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token(data={"sub": user.id})

        response = await client.post(
            "/api/auth/invite",
            cookies={"access_token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert len(data["code"]) > 0


@pytest.mark.asyncio
class TestAuthLogout:
    """Тесты выхода."""

    async def test_logout(self, client: AsyncClient):
        """Выход удаляет cookie."""
        response = await client.post("/api/auth/logout")
        assert response.status_code == 200
