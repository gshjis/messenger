"""Тесты для health endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Проверка работоспособности приложения."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_check_version(client: AsyncClient):
    """Проверка версии в health endpoint."""
    response = await client.get("/health")
    data = response.json()
    assert data["version"] == "0.1.0"
