"""
AI Provider Configuration Service

Manages AI provider configurations in the database with:
- CRUD operations
- Priority ordering
- Health status updates
- Delegates model fetching to provider classes
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AIProviderConfigModel
from app.services.ai.encryption import encrypt_secret
from app.services.ai.providers import PROVIDER_REGISTRY

logger = structlog.get_logger()


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

        # Use default URL from provider if not provided
        if not api_url:
            provider_cls = PROVIDER_REGISTRY.get(provider_type)
            if provider_cls:
                api_url = provider_cls.get_default_url()

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

    # -------------------------------------------------------------------------
    # Model Fetching (delegated to providers)
    # -------------------------------------------------------------------------

    @staticmethod
    async def get_models_for_provider(provider_type: str) -> dict[str, Any]:
        """Get available models for a provider.
        
        Delegates to the provider's class methods.
        
        Returns:
            Dict with models, default model, and reasoning_options
        """
        provider_cls = PROVIDER_REGISTRY.get(provider_type)
        if not provider_cls:
            return {"models": [], "default": "", "reasoning_options": None}

        return {
            "models": await provider_cls.get_available_models(),
            "default": provider_cls.get_default_model(),
            "reasoning_options": provider_cls.get_reasoning_options(),
            "provider_info": provider_cls.get_provider_info(),
        }

    @staticmethod
    def get_default_url(provider_type: str) -> str | None:
        """Get default API URL for a provider."""
        provider_cls = PROVIDER_REGISTRY.get(provider_type)
        if provider_cls:
            return provider_cls.get_default_url()
        return None
