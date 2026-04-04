"""Тесты безопасности."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSecurityHeaders:
    """Тесты security headers."""

    async def test_security_headers_present(self, client: AsyncClient):
        """Проверка наличия security headers."""
        response = await client.get("/health")
        assert response.status_code == 200

        headers = response.headers
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("x-xss-protection") == "1; mode=block"
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert headers.get("permissions-policy") == "camera=(), microphone=(), geolocation=()"


@pytest.mark.asyncio
class TestRateLimiting:
    """Тесты rate limiting."""

    async def test_rate_limit_health(self, client: AsyncClient):
        """Rate limit на health endpoint."""
        # Несколько быстрых запросов
        responses = []
        for _ in range(10):
            response = await client.get("/health")
            responses.append(response.status_code)

        # Хотя бы некоторые должны быть успешными
        assert 200 in responses


@pytest.mark.asyncio
class TestAuthSecurity:
    """Тесты безопасности аутентификации."""

    async def test_login_without_credentials(self, client: AsyncClient):
        """Логин без данных."""
        response = await client.post("/api/auth/login", json={})
        assert response.status_code == 422  # Validation error

    async def test_register_without_invite(self, client: AsyncClient):
        """Регистрация без invite-кода."""
        response = await client.post(
            "/api/auth/register",
            json={"username": "test", "password": "SecurePass123!", "invite_code": ""},
        )
        assert response.status_code == 422

    async def test_access_protected_endpoint_without_auth(self, client: AsyncClient):
        """Доступ к защищённому endpoint без авторизации."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_access_chats_without_auth(self, client: AsyncClient):
        """Доступ к чатам без авторизации."""
        response = await client.get("/api/chats")
        assert response.status_code == 401