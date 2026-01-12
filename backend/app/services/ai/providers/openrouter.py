"""
OpenRouter Provider

Adapter for OpenRouter API - a multi-model routing service.
"""

from app.db import AIProviderConfigModel
from app.services.ai.providers.base import BaseProvider


class OpenRouterProvider(BaseProvider):
    """OpenRouter provider adapter.

    OpenRouter provides access to multiple models through a single API.
    It uses the OpenAI-compatible API format with additional headers
    for app identification.
    """

    def __init__(self, config: AIProviderConfigModel):
        super().__init__(config)

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def _get_default_headers(self) -> dict[str, str]:
        """Add OpenRouter-specific headers for app identification."""
        return {
            "HTTP-Referer": "https://github.com/KyleDerZweite/dno-crawler",
            "X-Title": "DNO Crawler",
        }
