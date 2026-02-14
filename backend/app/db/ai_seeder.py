"""
Seeder for AI configurations.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import AIProviderConfigModel
from app.services.ai.config_service import AIConfigService
from app.services.ai.providers.openrouter import OpenRouterProvider

logger = structlog.get_logger()


async def seed_ai_config(db: AsyncSession) -> None:
    """
    Seed AI configuration from environment variables.

    If OPENROUTER_KEY is set in settings, create/update the OpenRouter configuration.
    """
    if not settings.openrouter_key:
        return

    logger.info("Seeding OpenRouter configuration from environment")

    # Check if OpenRouter config already exists
    result = await db.execute(
        select(AIProviderConfigModel).where(AIProviderConfigModel.provider_type == "openrouter")
    )
    existing_config = result.scalars().first()

    config_service = AIConfigService(db)

    if existing_config:
        logger.info("Updating existing OpenRouter configuration with environment key")
        await config_service.update(
            config_id=existing_config.id,
            api_key=settings.openrouter_key,
            is_enabled=True,
            supports_files=True,
        )
    else:
        logger.info("Creating new OpenRouter configuration from environment")
        await config_service.create(
            name="OpenRouter (Auto)",
            provider_type="openrouter",
            auth_type="api_key",
            model=OpenRouterProvider.DEFAULT_MODEL,
            api_key=settings.openrouter_key,
            api_url=OpenRouterProvider.API_URL,
            supports_text=True,
            supports_vision=True,
            supports_files=True,
        )

    await db.commit()
    logger.info("AI configuration seeded successfully")
