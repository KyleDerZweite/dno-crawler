"""
Smoke tests for DNO endpoints.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestDNOEndpoints:
    async def test_list_dnos_empty(self, client: AsyncClient) -> None:
        """Test listing DNOs returns empty list initially."""
        response = await client.get("/api/v1/dnos")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "meta" in data
        assert isinstance(data["data"], list)

    async def test_list_dnos_pagination_params(self, client: AsyncClient) -> None:
        """Test DNO listing accepts pagination parameters."""
        response = await client.get("/api/v1/dnos?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert "meta" in data
        assert "page" in data["meta"]
        assert "page_size" in data["meta"]

    async def test_get_dno_not_found(self, client: AsyncClient) -> None:
        """Test getting non-existent DNO returns 404."""
        response = await client.get("/api/v1/dnos/99999")
        assert response.status_code == 404
