"""
Smoke tests for authentication.
"""

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


class TestAuthEndpoints:
    async def test_me_endpoint_mock_mode(self, client: AsyncClient) -> None:
        """In mock mode (ZITADEL_DOMAIN=auth.example.com), /me returns mock admin user."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "name" in data
        assert "roles" in data
        assert "is_admin" in data
        assert data["is_admin"] is True

    async def test_me_endpoint_returns_user_structure(self, client: AsyncClient) -> None:
        """Verify /me response structure."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["id"], str)
        assert isinstance(data["email"], str)
        assert isinstance(data["name"], str)
        assert isinstance(data["roles"], list)
        assert isinstance(data["is_admin"], bool)