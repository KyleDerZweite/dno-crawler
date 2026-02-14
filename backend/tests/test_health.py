"""
Smoke tests for health endpoints.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestHealthEndpoints:
    async def test_health_check_returns_healthy(self, client: AsyncClient) -> None:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    async def test_readiness_check_structure(self, client: AsyncClient) -> None:
        response = await client.get("/api/ready")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data
        assert data["status"] in ("ready", "degraded")
