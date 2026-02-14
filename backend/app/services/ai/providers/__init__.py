"""
Provider Adapters Package

Contains implementations for each supported AI provider.
To add a new provider:
1. Create a new file (e.g., myprovider.py) implementing BaseProvider
2. Import it here and add to PROVIDER_REGISTRY

The registry is the single source of truth - frontend fetches from it dynamically.
"""

from app.services.ai.providers.base import BaseProvider
from app.services.ai.providers.custom import CustomProvider
from app.services.ai.providers.litellm import LiteLLMProvider
from app.services.ai.providers.openrouter import OpenRouterProvider

# Registry mapping provider_type string -> provider class
# This is the ONLY place you need to add a new provider
PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "openrouter": OpenRouterProvider,
    "litellm": LiteLLMProvider,
    "custom": CustomProvider,
}


def get_all_providers() -> dict[str, dict]:
    """Return info for all registered providers.

    Used by the frontend to dynamically build provider selection UI.
    """
    result = {}
    for provider_type, provider_cls in PROVIDER_REGISTRY.items():
        result[provider_type] = provider_cls.get_provider_info()
    return result


__all__ = [
    "PROVIDER_REGISTRY",
    "BaseProvider",
    "CustomProvider",
    "LiteLLMProvider",
    "OpenRouterProvider",
    "get_all_providers",
]
