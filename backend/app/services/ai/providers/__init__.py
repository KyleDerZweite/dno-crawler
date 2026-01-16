"""
Provider Adapters Package

Contains implementations for each supported AI provider:
- OpenRouter (primary, with native SDK)
- LiteLLM (stub for future proxy support)
- Custom (generic OpenAI-compatible)
"""

from app.services.ai.providers.base import BaseProvider
from app.services.ai.providers.custom import CustomProvider
from app.services.ai.providers.litellm import LiteLLMProvider
from app.services.ai.providers.openrouter import OpenRouterProvider

__all__ = [
    "BaseProvider",
    "CustomProvider",
    "LiteLLMProvider",
    "OpenRouterProvider",
]
