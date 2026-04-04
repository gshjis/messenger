"""Тесты для аутентификации."""

import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.models.invite_code import InviteCode
from messenger.models.user import User
from messenger.security.auth import create_access_token, hash_password


@pytest.mark.asyncio
class TestAuthLogin:
    """Тесты логина."""

    async def test_login_success(self, client: AsyncClient, test_session: AsyncSession) -> None:
        """Успешный логин."""
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

    async def test_login_wrong_password(self, client: AsyncClient, test_session: AsyncSession) -> None:
        """Неверный пароль."""
        user = User(username="wrongpass", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()

        response = await client.post(
            "/api/auth/login",
            json={"username": "wrongpass", "password": "WrongPassword"},
        )

        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        """Несуществующий пользователь."""
        response = await client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "SecurePass123!"},
        )

        assert response.status_code == 401

    async def test_login_banned_user(self, client: AsyncClient, test_session: AsyncSession) -> None:
        """Забаненный пользователь."""
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

    async def test_register_success(self, client: AsyncClient, test_session: AsyncSession) -> None:
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

    async def test_register_invalid_invite(self, client: AsyncClient) -> None:
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

    async def test_register_duplicate_username(self, client: AsyncClient, test_session: AsyncSession) -> None:
        """Регистрация с занятым username."""
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

    async def test_register_used_invite(self, client: AsyncClient, test_session: AsyncSession) -> None:
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

    async def test_get_me_authenticated(self, auth_client: AsyncClient, test_user: User) -> None:
        """Получение данных авторизованного пользователя."""
        response = await auth_client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username
        assert data["id"] == test_user.id

    async def test_get_me_no_token(self, client: AsyncClient) -> None:
        """Получение данных без токена."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_get_me_invalid_token(self, client: AsyncClient) -> None:
        """Получение данных с невалидным токеном."""
        response = await client.get(
            "/api/auth/me",
            cookies={"access_token": "invalid.token.here"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestAuthProfile:
    """Тесты обновления профиля."""

    async def test_update_username(self, auth_client: AsyncClient) -> None:
        """Смена username."""
        response = await auth_client.put(
            "/api/auth/me",
            json={"username": "newname"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newname"

    async def test_update_duplicate_username(self, auth_client: AsyncClient, test_session: AsyncSession) -> None:
        """Смена username на занятый."""
        user2 = User(username="user2", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user2)
        await test_session.commit()

        response = await auth_client.put(
            "/api/auth/me",
            json={"username": "user2"},
        )
        assert response.status_code == 400


@pytest.mark.asyncio
class TestAuthInvite:
    """Тесты генерации invite-кодов."""

    async def test_generate_invite(self, auth_client: AsyncClient) -> None:
        """Генерация invite-кода."""
        response = await auth_client.post("/api/auth/invite")
        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert len(data["code"]) > 0


@pytest.mark.asyncio
class TestAuthLogout:
    """Тесты выхода."""

    async def test_logout(self, client: AsyncClient) -> None:
        """Выход удаляет cookie."""
        response = await client.post("/api/auth/logout")
        assert response.status_code == 200
