"""
OpenAI Provider

Adapter for OpenAI API (GPT models).
"""

from app.db import AIProviderConfigModel
from app.services.ai.providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    """OpenAI provider adapter.
    
    Uses the standard OpenAI API endpoint.
    Default URL: https://api.openai.com/v1
    """
    
    def __init__(self, config: AIProviderConfigModel):
        super().__init__(config)
    
    @property
    def provider_name(self) -> str:
        return "openai"
