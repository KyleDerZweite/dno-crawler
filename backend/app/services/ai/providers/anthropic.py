"""
Anthropic Provider

Adapter for Anthropic API (Claude models).
"""

from app.db import AIProviderConfigModel
from app.services.ai.providers.base import BaseProvider


class AnthropicProvider(BaseProvider):
    """Anthropic provider adapter.
    
    Uses the Anthropic API endpoint.
    Default URL: https://api.anthropic.com/v1
    
    Note: Anthropic's native API differs from OpenAI's format.
    For now, this uses the compatibility layer. A future version
    could implement native Anthropic API calls.
    """
    
    def __init__(self, config: AIProviderConfigModel):
        super().__init__(config)
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
