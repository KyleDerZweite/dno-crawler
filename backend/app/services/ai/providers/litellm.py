"""
LiteLLM Provider (Stub)

Placeholder for future LiteLLM proxy server support.
Currently returns NotImplementedError for all operations.
"""

from typing import Any

import structlog

from app.db import AIProviderConfigModel
from app.services.ai.providers.base import BaseProvider

logger = structlog.get_logger()


class LiteLLMProvider(BaseProvider):
    """LiteLLM proxy provider - Coming Soon.
    
    This provider will eventually support:
    - Connection to LiteLLM proxy servers
    - Access to any model the proxy exposes
    - Unified interface for enterprise deployments
    """
    
    def __init__(self, config: AIProviderConfigModel):
        super().__init__(config)
    
    @property
    def provider_name(self) -> str:
        return "litellm"
    
    # -------------------------------------------------------------------------
    # Class Methods
    # -------------------------------------------------------------------------
    
    @classmethod
    async def get_available_models(cls) -> list[dict[str, Any]]:
        """Return empty list - LiteLLM not yet implemented."""
        return []
    
    @classmethod
    def get_default_model(cls) -> str:
        """No default model for LiteLLM stub."""
        return ""
    
    @classmethod
    def get_default_url(cls) -> str | None:
        """Default would be local proxy."""
        return "http://localhost:4000"
    
    @classmethod
    def get_reasoning_options(cls) -> dict[str, Any] | None:
        """LiteLLM doesn't have standard reasoning options."""
        return None
    
    # -------------------------------------------------------------------------
    # Instance Methods
    # -------------------------------------------------------------------------
    
    async def extract_text(
        self,
        content: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Not implemented yet."""
        raise NotImplementedError(
            "LiteLLM provider is coming soon. "
            "Use OpenRouter or Custom provider for now."
        )
    
    async def extract_vision(
        self,
        image_data: str,
        mime_type: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Not implemented yet."""
        raise NotImplementedError(
            "LiteLLM provider is coming soon. "
            "Use OpenRouter or Custom provider for now."
        )
    
    async def health_check(self) -> bool:
        """Always return False for stub."""
        return False
