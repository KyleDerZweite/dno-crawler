"""
AI Service Package

Provides a modular, multi-provider AI extraction gateway with:
- Provider abstraction layer (OpenAI, Google, Anthropic, OpenRouter, etc.)
- Admin-configurable provider management
- Smart fallback on rate limits
- OAuth and API key authentication support
- Dynamic model registry from models.dev
"""

from app.services.ai.gateway import AIGateway, get_ai_gateway
from app.services.ai.interface import AIProviderInterface
from app.services.ai.models_registry import ModelsRegistry, get_models_for_provider

__all__ = [
    "AIGateway",
    "AIProviderInterface",
    "ModelsRegistry",
    "get_ai_gateway",
    "get_models_for_provider",
]

