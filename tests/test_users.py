"""Тесты для поиска пользователей."""

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from messenger.models.user import User
from messenger.security.auth import hash_password


@pytest.mark.asyncio
class TestUserSearch:
    """Тесты поиска пользователей."""

    async def test_search_users_success(self, auth_client: AsyncClient, test_session: AsyncSession) -> None:
        """Успешный поиск пользователей."""
        # Создаём тестовых пользователей
        users = [
            User(username="alice", hashed_password=hash_password("SecurePass123!")),
            User(username="bob", hashed_password=hash_password("SecurePass123!")),
            User(username="alex", hashed_password=hash_password("SecurePass123!")),
        ]
        for user in users:
            test_session.add(user)
        await test_session.commit()

        response = await auth_client.get("/api/users/search?q=al")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # alice и alex
        usernames = [u["username"] for u in data]
        assert "alice" in usernames
        assert "alex" in usernames
        assert "bob" not in usernames

    async def test_search_users_no_results(self, auth_client: AsyncClient) -> None:
        """Поиск без результатов."""
        response = await auth_client.get("/api/users/search?q=nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    async def test_search_users_excludes_self(self, auth_client: AsyncClient, test_user: User) -> None:
        """Поиск исключает текущего пользователя."""
        response = await auth_client.get(f"/api/users/search?q={test_user.username}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0  # Текущий пользователь исключён

    async def test_search_users_case_insensitive(self, auth_client: AsyncClient, test_session: AsyncSession) -> None:
        """Поиск регистронезависимый."""
        user = User(username="TestUser", hashed_password=hash_password("SecurePass123!"))
        test_session.add(user)
        await test_session.commit()

        response = await auth_client.get("/api/users/search?q=test")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["username"] == "TestUser"

    async def test_search_users_unauthorized(self, client: AsyncClient) -> None:
        """Поиск без авторизации."""
        response = await client.get("/api/users/search?q=test")
        assert response.status_code == 401

    async def test_search_users_empty_query(self, auth_client: AsyncClient) -> None:
        """Поиск с пустым запросом."""
        response = await auth_client.get("/api/users/search?q=")
        assert response.status_code == 422  # Validation error

    async def test_search_users_limit(self, auth_client: AsyncClient, test_session: AsyncSession) -> None:
        """Поиск с ограничением лимита."""
        for i in range(30):
            user = User(username=f"user{i}", hashed_password=hash_password("SecurePass123!"))
            test_session.add(user)
        await test_session.commit()

        response = await auth_client.get("/api/users/search?q=user&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5
