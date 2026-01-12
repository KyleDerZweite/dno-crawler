"""
AI Provider Configuration Service

Manages AI provider configurations in the database with:
- CRUD operations
- Caching for active configs
- Priority ordering
- Health status updates
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AIProviderConfigModel
from app.services.ai.encryption import encrypt_secret

# Import shared model definitions (Source of Truth)
from app.services.ai.models_registry import FALLBACK_MODELS

logger = structlog.get_logger()

# Cache TTL for active configs
CONFIG_CACHE_TTL_SECONDS = 60

# Provider default URLs
PROVIDER_DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "anthropic": "https://api.anthropic.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


class AIConfigService:
    """Service for managing AI provider configurations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> Sequence[AIProviderConfigModel]:
        """List all AI provider configs, ordered by priority."""
        result = await self.db.execute(
            select(AIProviderConfigModel)
            .order_by(AIProviderConfigModel.priority)
        )
        return result.scalars().all()

    async def list_enabled(self) -> Sequence[AIProviderConfigModel]:
        """List enabled AI provider configs, ordered by priority."""
        result = await self.db.execute(
            select(AIProviderConfigModel)
            .where(AIProviderConfigModel.is_enabled)
            .order_by(AIProviderConfigModel.priority)
        )
        return result.scalars().all()

    async def get_by_id(self, config_id: int) -> AIProviderConfigModel | None:
        """Get a config by ID."""
        result = await self.db.execute(
            select(AIProviderConfigModel)
            .where(AIProviderConfigModel.id == config_id)
        )
        return result.scalar_one_or_none()

    async def get_active_config(self) -> AIProviderConfigModel | None:
        """Get the highest priority enabled config that is healthy."""
        configs = await self.list_enabled()

        for config in configs:
            if config.is_healthy:
                return config

        # All unhealthy, return first enabled anyway
        return configs[0] if configs else None

    async def create(
        self,
        name: str,
        provider_type: str,
        auth_type: str,
        model: str,
        api_key: str | None = None,
        api_url: str | None = None,
        supports_text: bool = True,
        supports_vision: bool = False,
        supports_files: bool = False,
        model_parameters: dict | None = None,
        created_by: str | None = None,
    ) -> AIProviderConfigModel:
        """Create a new AI provider config."""
        # Get next priority
        existing = await self.list_all()
        next_priority = len(existing)

        # Use default URL if not provided
        if not api_url and provider_type in PROVIDER_DEFAULT_URLS:
            api_url = PROVIDER_DEFAULT_URLS[provider_type]

        config = AIProviderConfigModel(
            name=name,
            provider_type=provider_type,
            auth_type=auth_type,
            model=model,
            api_url=api_url,
            api_key_encrypted=encrypt_secret(api_key) if api_key else None,
            supports_text=supports_text,
            supports_vision=supports_vision,
            supports_files=supports_files,
            model_parameters=model_parameters,
            priority=next_priority,
            created_by=created_by,
        )

        self.db.add(config)
        await self.db.flush()

        logger.info(
            "ai_config_created",
            config_id=config.id,
            provider=provider_type,
            model=model,
            created_by=created_by,
        )

        return config

    async def update(
        self,
        config_id: int,
        name: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        api_url: str | None = None,
        supports_text: bool | None = None,
        supports_vision: bool | None = None,
        supports_files: bool | None = None,
        model_parameters: dict | None = None,
        is_enabled: bool | None = None,
        modified_by: str | None = None,
    ) -> AIProviderConfigModel | None:
        """Update an existing config."""
        config = await self.get_by_id(config_id)
        if not config:
            return None

        if name is not None:
            config.name = name
        if model is not None:
            config.model = model
        if api_key is not None:
            config.api_key_encrypted = encrypt_secret(api_key)
        if api_url is not None:
            config.api_url = api_url
        if supports_text is not None:
            config.supports_text = supports_text
        if supports_vision is not None:
            config.supports_vision = supports_vision
        if supports_files is not None:
            config.supports_files = supports_files
        if model_parameters is not None:
            config.model_parameters = model_parameters
        if is_enabled is not None:
            config.is_enabled = is_enabled
        if modified_by:
            config.last_modified_by = modified_by

        await self.db.flush()

        logger.info(
            "ai_config_updated",
            config_id=config_id,
            modified_by=modified_by,
        )

        return config

    async def delete(self, config_id: int) -> bool:
        """Delete a config."""
        config = await self.get_by_id(config_id)
        if not config:
            return False

        await self.db.delete(config)
        await self.db.flush()

        logger.info("ai_config_deleted", config_id=config_id)
        return True

    async def reorder(self, config_ids: list[int]) -> bool:
        """Reorder configs by setting priorities.

        Args:
            config_ids: List of config IDs in desired order

        Returns:
            True if successful
        """
        for priority, config_id in enumerate(config_ids):
            await self.db.execute(
                update(AIProviderConfigModel)
                .where(AIProviderConfigModel.id == config_id)
                .values(priority=priority)
            )

        await self.db.flush()
        logger.info("ai_configs_reordered", order=config_ids)
        return True

    async def mark_success(self, config_id: int, tokens_used: int = 0) -> None:
        """Mark a successful request."""
        await self.db.execute(
            update(AIProviderConfigModel)
            .where(AIProviderConfigModel.id == config_id)
            .values(
                last_success_at=datetime.now(UTC),
                consecutive_failures=0,
                rate_limited_until=None,
                total_requests=AIProviderConfigModel.total_requests + 1,
                total_tokens_used=AIProviderConfigModel.total_tokens_used + tokens_used,
            )
        )

    async def mark_failure(self, config_id: int, error_message: str) -> None:
        """Mark a failed request."""
        await self.db.execute(
            update(AIProviderConfigModel)
            .where(AIProviderConfigModel.id == config_id)
            .values(
                last_error_at=datetime.now(UTC),
                last_error_message=error_message,
                consecutive_failures=AIProviderConfigModel.consecutive_failures + 1,
            )
        )

    async def mark_rate_limited(self, config_id: int, retry_after_seconds: int = 60) -> None:
        """Mark a rate limit hit."""
        until = datetime.now(UTC) + timedelta(seconds=retry_after_seconds)
        await self.db.execute(
            update(AIProviderConfigModel)
            .where(AIProviderConfigModel.id == config_id)
            .values(
                rate_limited_until=until,
                last_error_at=datetime.now(UTC),
                last_error_message=f"Rate limited until {until.isoformat()}",
            )
        )

    @staticmethod
    def get_models_for_provider_sync(provider_type: str) -> list[dict]:
        """Get available models for a provider (sync fallback).

        Use get_models_for_provider() for full model list from models.dev.
        """
        return FALLBACK_MODELS.get(provider_type, [])

    @staticmethod
    def get_suggested_models(provider_type: str) -> list[dict]:
        """Get the curated list of suggested/recommended models for a provider.

        This returns only the FALLBACK_MODELS - a hand-picked list of the best
        and most current models. Used as the default display before user searches.
        """
        return FALLBACK_MODELS.get(provider_type, [])

    @staticmethod
    async def search_models_for_provider(
        provider_type: str,
        query: str = "",
        supports_vision: bool | None = None,
        supports_files: bool | None = None,
        limit: int = 25,
    ) -> list[dict]:
        """Search models for a provider from the full models.dev registry.

        Used when the user actively searches/types to find models beyond
        the suggested list. Returns fuzzy-matched results from the full registry.

        Args:
            provider_type: Provider to search (openai, google, anthropic, etc.)
            query: Search query for model name/ID
            supports_vision: Optional filter for vision capability
            supports_files: Optional filter for file/PDF capability
            limit: Max results to return

        Returns:
            List of matching models from the registry
        """
        try:
            from app.services.ai.models_registry import search_models as registry_search

            models = await registry_search(
                query=query,
                provider=provider_type if provider_type not in ("litellm", "custom") else None,
                supports_vision=supports_vision,
                supports_files=supports_files,
                limit=limit,
            )
            return models
        except Exception as e:
            logger.warning("models_registry_search_failed", error=str(e), query=query)

            # Fallback: filter FALLBACK_MODELS locally
            fallback = FALLBACK_MODELS.get(provider_type, [])
            if not query:
                return fallback[:limit]

            query_lower = query.lower()
            return [
                m for m in fallback
                if query_lower in m["id"].lower() or query_lower in m["name"].lower()
            ][:limit]

    @staticmethod
    async def get_models_for_provider(provider_type: str) -> list[dict]:
        """Get available models for a provider from models.dev registry.

        Falls back to hardcoded list if registry unavailable.
        """
        try:
            from app.services.ai.models_registry import (
                get_models_for_provider as registry_get_models,
            )
            models = await registry_get_models(provider_type)
            if models:
                return models
        except Exception as e:
            logger.warning("models_registry_unavailable", error=str(e))

        # Fallback to hardcoded list
        return FALLBACK_MODELS.get(provider_type, [])

    @staticmethod
    def get_default_url(provider_type: str) -> str | None:
        """Get default API URL for a provider."""
        return PROVIDER_DEFAULT_URLS.get(provider_type)


async def refresh_models_registry() -> bool:
    """Refresh the models registry cache from models.dev API."""
    from app.services.ai.models_registry import refresh_models_cache
    return await refresh_models_cache()


def get_models_registry_status() -> dict:
    """Get status of the models registry cache."""
    from app.services.ai.models_registry import ModelsRegistry
    return ModelsRegistry.get_instance().get_cache_status()
