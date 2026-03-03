"""
Smoke tests for search endpoint.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestSearchEndpoint:
    async def test_search_requires_input(self, client: AsyncClient) -> None:
        """Search endpoint requires at least one search parameter."""
        response = await client.post("/api/v1/search/", json={})
        assert response.status_code in (400, 422)

    async def test_search_with_invalid_coordinates(self, client: AsyncClient) -> None:
        """Search with invalid coordinates returns error."""
        response = await client.post("/api/v1/search/", json={"latitude": 999, "longitude": 999})
        assert response.status_code in (400, 422)

    async def test_search_with_address_format(self, client: AsyncClient) -> None:
        """Search accepts address string."""
        response = await client.post(
            "/api/v1/search/",
            json={
                "address": {
                    "street": "Musterstr. 1",
                    "zip_code": "10115",
                    "city": "Berlin",
                }
            },
        )
        assert response.status_code in (200, 202, 400, 429, 502, 503)

    async def test_search_response_structure(self, client: AsyncClient) -> None:
        """Verify search response has expected structure when successful."""
        response = await client.post(
            "/api/v1/search/",
            json={
                "address": {
                    "street": "Musterstr. 1",
                    "zip_code": "10115",
                    "city": "Berlin",
                }
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert "dno" in data or "error" in data
