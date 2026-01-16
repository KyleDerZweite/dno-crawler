"""
AI Service Package

Provides a modular, multi-provider AI extraction gateway with:
- Provider abstraction layer (OpenRouter, LiteLLM, Custom)
- Admin-configurable provider management
- Smart fallback on rate limits
- API key authentication
"""

from app.services.ai.config_service import AIConfigService
from app.services.ai.gateway import AIGateway, get_ai_gateway
from app.services.ai.providers.base import BaseProvider

__all__ = [
    "AIConfigService",
    "AIGateway",
    "BaseProvider",
    "get_ai_gateway",
]

