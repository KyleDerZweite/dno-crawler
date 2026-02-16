"""
Pytest configuration and fixtures for DNO Crawler tests.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.main import app
from app.db.database import Base, async_session_maker, engine


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


async def _create_tables() -> None:
    """Create pg_trgm extension and all tables."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        await conn.run_sync(Base.metadata.create_all)


async def _drop_tables() -> None:
    """Drop all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    await _create_tables()

    async with async_session_maker() as session:
        yield session
        await session.rollback()

    await _drop_tables()


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing with a fresh database."""
    await _create_tables()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    await _drop_tables()


@pytest.fixture
def mock_auth_headers() -> dict[str, str]:
    """Headers for mock auth mode (ZITADEL_DOMAIN=auth.example.com).

    In mock mode, the auth middleware automatically creates a mock admin user.
    No headers needed.
    """
    return {}
