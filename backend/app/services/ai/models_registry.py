"""
AI Models Registry - Dynamic Model Catalog

Fetches and caches model information from models.dev API.
Provides full catalog with pricing, capabilities, and provider details.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

# Cache file location
CACHE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "cache"
MODELS_CACHE_FILE = CACHE_DIR / "models_registry.json"
CACHE_MAX_AGE_HOURS = 24  # Refresh cache every 24 hours

# Models.dev API endpoint
MODELS_API_URL = "https://models.dev/api.json"

# Provider ID mapping (models.dev provider ID -> our provider type)
PROVIDER_MAPPING = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google",
    "google-vertex": "google",
    "mistral": "mistral",
    "xai": "xai",
    "cohere": "cohere",
    "groq": "groq",
    "deepseek": "deepseek",
    "alibaba": "alibaba",
    "meta": "meta",
    "nvidia": "nvidia",
}

# OpenRouter uses provider/model format, list providers available via OpenRouter
OPENROUTER_PROVIDERS = {
    "openai", "anthropic", "google", "mistral", "xai", "meta",
    "deepseek", "cohere", "qwen", "nvidia", "perplexity"
}

# Fallback/Known models with explicit capabilities (Source of Truth for Thinking)
FALLBACK_MODELS = {
    "openai": [
        # Hypothetical Future Models (Assumed standard behavior)
        {"id": "gpt-5", "name": "GPT-5", "supports_vision": True, "supports_files": False, "tier": "efficient"},
        {"id": "gpt-5.2", "name": "GPT-5.2", "supports_vision": True, "supports_files": False, "tier": "efficient"},
        {"id": "gpt-5-mini", "name": "GPT-5 Mini", "supports_vision": True, "supports_files": False, "tier": "budget"},
        
        # Reasoning Models (Level-based)
        {"id": "o3-mini", "name": "o3 Mini (Reasoning)", "supports_vision": True, "supports_files": False, "tier": "efficient", 
         "thinking_capability": {"method": "level", "options": ["low", "medium", "high"], "default": "medium", "can_disable": False}},
        {"id": "o4-mini", "name": "o4 Mini (Reasoning)", "supports_vision": True, "supports_files": False, "tier": "efficient",
         "thinking_capability": {"method": "level", "options": ["low", "medium", "high"], "default": "medium", "can_disable": False}},
        
        # Standard
        {"id": "gpt-4o", "name": "GPT-4o", "supports_vision": True, "supports_files": False, "tier": "efficient"}
    ],
    "google": [
        # Gemini 3 Series (Level-based)
        {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash", "supports_vision": True, "supports_files": True, "tier": "efficient",
         "thinking_capability": {"method": "level", "options": ["minimal", "low", "medium", "high"], "default": "high", "can_disable": False}}, 
         # Note: 'minimal' is the closest to off for G3 Flash
         
        {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro", "supports_vision": True, "supports_files": True, "tier": "high",
         "thinking_capability": {"method": "level", "options": ["low", "high"], "default": "high", "can_disable": False}},

        # Gemini 2.5 Series (Budget-based)
        {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "supports_vision": True, "supports_files": True, "tier": "efficient",
         "thinking_capability": {"method": "budget", "min": 0, "max": 24576, "default": -1, "can_disable": True, "dynamic_param": -1}},
         # Note: -1 enables Dynamic Thinking

        {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite", "supports_vision": True, "supports_files": True, "tier": "budget",
         "thinking_capability": {"method": "budget", "min": 512, "max": 24576, "default": 0, "can_disable": True, "dynamic_param": -1}},
         # Lite defaults to NO thinking (0), but can be forced via budget or dynamic (-1)

        # Legacy / Experimental
        {"id": "gemini-2.0-flash-thinking-exp", "name": "Gemini 2.0 Flash Thinking", "supports_vision": True, "supports_files": True, "tier": "efficient",
         "thinking_capability": {"method": "budget", "min": 1024, "max": 32768, "default": 0, "can_disable": True}}
    ],
    "anthropic": [
        # Hypothetical Future Models (Assumed to inherit Sonnet 3.7 traits)
        {"id": "claude-sonnet-4-5-20250929", "name": "Claude 4.5 Sonnet", "supports_vision": True, "supports_files": True, "tier": "efficient",
         "thinking_capability": {"method": "budget", "min": 1024, "max": 64000, "default": 16000, "can_disable": True}},
        
        {"id": "claude-haiku-4-5", "name": "Claude 4.5 Haiku", "supports_vision": True, "supports_files": True, "tier": "budget"},
        
        # Claude 3.7 (Budget-based)
        {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet", "supports_vision": True, "supports_files": True, "tier": "efficient",
         "thinking_capability": {"method": "budget", "min": 1024, "max": 64000, "default": 16000, "can_disable": True}}
    ],
    "openrouter": [
        {"id": "openai/gpt-5", "name": "GPT-5", "supports_vision": True, "supports_files": False, "tier": "efficient"},
        
        {"id": "google/gemini-2.0-flash-thinking-exp", "name": "Gemini 2.0 Flash Thinking", "supports_vision": True, "supports_files": True, "tier": "efficient",
         "thinking_capability": {"method": "budget", "min": 1024, "max": 32768, "default": 0, "can_disable": True}},
         
        {"id": "anthropic/claude-3.7-sonnet", "name": "Claude 3.7 Sonnet", "supports_vision": True, "supports_files": True, "tier": "efficient",
         "thinking_capability": {"method": "budget", "min": 1024, "max": 64000, "default": 16000, "can_disable": True}},
         
        {"id": "deepseek/deepseek-v3.2", "name": "DeepSeek V3.2", "supports_vision": False, "supports_files": False, "tier": "budget"}
    ],
    "litellm": [],
    "custom": []
}


class ModelsRegistry:
    """Dynamic model registry with caching from models.dev API."""

    _instance: "ModelsRegistry | None" = None
    _cache: dict[str, Any] = {}
    _cache_loaded_at: datetime | None = None

    def __new__(cls) -> "ModelsRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ModelsRegistry":
        """Get singleton instance."""
        return cls()

    async def ensure_loaded(self) -> None:
        """Ensure models cache is loaded."""
        if self._cache and self._cache_loaded_at:
            age_hours = (datetime.now(UTC) - self._cache_loaded_at).total_seconds() / 3600
            if age_hours < CACHE_MAX_AGE_HOURS:
                return  # Cache is fresh

        # Try to load from file cache
        if await self._load_from_file():
            return

        # Fetch from API
        await self.refresh()

    async def refresh(self) -> bool:
        """Refresh model data from models.dev API."""
        try:
            logger.info("models_registry_refresh_start")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(MODELS_API_URL)
                response.raise_for_status()
                data = response.json()

            self._cache = data
            self._cache_loaded_at = datetime.now(UTC)

            # Save to file cache
            await self._save_to_file()

            logger.info(
                "models_registry_refresh_complete",
                providers=len(data),
                total_models=sum(len(p.get("models", {})) for p in data.values()),
            )
            return True

        except Exception as e:
            logger.error("models_registry_refresh_failed", error=str(e))
            return False

    async def _load_from_file(self) -> bool:
        """Load from file cache if exists and fresh."""
        try:
            if not MODELS_CACHE_FILE.exists():
                return False

            # Check file age
            mtime = datetime.fromtimestamp(MODELS_CACHE_FILE.stat().st_mtime, tz=UTC)
            age_hours = (datetime.now(UTC) - mtime).total_seconds() / 3600

            if age_hours > CACHE_MAX_AGE_HOURS:
                logger.info("models_cache_expired", age_hours=age_hours)
                return False

            with open(MODELS_CACHE_FILE) as f:
                self._cache = json.load(f)

            self._cache_loaded_at = mtime
            logger.info("models_cache_loaded_from_file", age_hours=round(age_hours, 1))
            return True

        except Exception as e:
            logger.warning("models_cache_load_failed", error=str(e))
            return False

    async def _save_to_file(self) -> None:
        """Save to file cache."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(MODELS_CACHE_FILE, "w") as f:
                json.dump(self._cache, f)
            logger.debug("models_cache_saved")
        except Exception as e:
            logger.warning("models_cache_save_failed", error=str(e))

    def _get_known_capability(self, model_id: str) -> dict | None:
        """Get known capability for a model ID from FALLBACK_MODELS."""
        for provider_models in FALLBACK_MODELS.values():
            for model in provider_models:
                if model["id"] == model_id:
                    return model.get("thinking_capability")
        return None

    def _transform_model(self, provider_id: str, model_id: str, model_data: dict) -> dict:
        """Transform models.dev model format to our format."""
        modalities = model_data.get("modalities", {})
        input_modalities = modalities.get("input", [])

        cost = model_data.get("cost", {})
        limit = model_data.get("limit", {})

        # Determine capabilities
        supports_vision = "image" in input_modalities
        supports_files = "pdf" in input_modalities or model_data.get("attachment", False)
        supports_audio = "audio" in input_modalities
        supports_video = "video" in input_modalities

        # Determine tier based on cost
        input_cost = cost.get("input", 0) or 0
        if input_cost == 0:
            tier = "free"
        elif input_cost < 0.2:
            tier = "budget"
        elif input_cost < 2:
            tier = "efficient"
        else:
            tier = "high"

        # Check for known thinking capabilities
        thinking_capability = self._get_known_capability(model_id)

        return {
            "id": model_id,
            "name": model_data.get("name", model_id),
            "provider": provider_id,
            "provider_name": self._cache.get(provider_id, {}).get("name", provider_id),
            "family": model_data.get("family", ""),

            # Capabilities
            "supports_vision": supports_vision,
            "supports_files": supports_files,
            "supports_audio": supports_audio,
            "supports_video": supports_video,
            "supports_text": True,  # All models support text
            "reasoning": model_data.get("reasoning", False),
            "tool_call": model_data.get("tool_call", False),
            "structured_output": model_data.get("structured_output", False),

            # Thinking Capability (Injected from FALLBACK_MODELS)
            "thinking_capability": thinking_capability,

            # Pricing (per million tokens)
            "cost_input": cost.get("input"),
            "cost_output": cost.get("output"),
            "cost_cache_read": cost.get("cache_read"),
            "cost_cache_write": cost.get("cache_write"),
            "cost_reasoning": cost.get("reasoning"),

            # Limits
            "context_limit": limit.get("context"),
            "output_limit": limit.get("output"),

            # Metadata
            "tier": tier,
            "release_date": model_data.get("release_date"),
            "knowledge_cutoff": model_data.get("knowledge"),
            "open_weights": model_data.get("open_weights", False),
            "status": model_data.get("status"),  # e.g., "deprecated"
        }

    async def get_models_for_provider(self, provider_type: str) -> list[dict]:
        """Get all models for a specific provider type.

        Args:
            provider_type: Our provider type (openai, google, anthropic, openrouter)

        Returns:
            List of model dicts with full details
        """
        await self.ensure_loaded()

        if provider_type == "openrouter":
            return await self._get_openrouter_models()

        # Find matching provider in cache
        for provider_id, provider_data in self._cache.items():
            if PROVIDER_MAPPING.get(provider_id) == provider_type:
                models = []
                for model_id, model_data in provider_data.get("models", {}).items():
                    # Skip deprecated models by default
                    if model_data.get("status") == "deprecated":
                        continue
                    models.append(self._transform_model(provider_id, model_id, model_data))

                # Sort by tier (high first), then by name
                tier_order = {"high": 0, "efficient": 1, "budget": 2, "free": 3}
                models.sort(key=lambda m: (tier_order.get(m["tier"], 99), m["name"]))
                return models

        return []

    async def _get_openrouter_models(self) -> list[dict]:
        """Get models available via OpenRouter (aggregates multiple providers)."""
        await self.ensure_loaded()

        models = []

        # Check the vercel provider which has lots of aggregated models with openrouter-style IDs
        vercel = self._cache.get("vercel", {})
        for model_id, model_data in vercel.get("models", {}).items():
            if model_data.get("status") == "deprecated":
                continue
            model = self._transform_model("vercel", model_id, model_data)
            # Use the model_id which is already in provider/model format
            model["id"] = model_id
            models.append(model)

        # Also add models from openrouter-compatible providers with prefixed IDs
        for provider_id, provider_data in self._cache.items():
            if provider_id in OPENROUTER_PROVIDERS:
                for model_id, model_data in provider_data.get("models", {}).items():
                    if model_data.get("status") == "deprecated":
                        continue
                    model = self._transform_model(provider_id, model_id, model_data)
                    # Prefix with provider for OpenRouter format
                    model["id"] = f"{provider_id}/{model_id}"
                    models.append(model)

        # Sort and dedupe
        seen = set()
        unique_models = []
        for m in models:
            if m["id"] not in seen:
                seen.add(m["id"])
                unique_models.append(m)

        tier_order = {"high": 0, "efficient": 1, "budget": 2, "free": 3}
        unique_models.sort(key=lambda m: (tier_order.get(m["tier"], 99), m["name"]))

        return unique_models

    async def search_models(
        self,
        query: str = "",
        provider: str | None = None,
        supports_vision: bool | None = None,
        supports_files: bool | None = None,
        tier: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search models with filters.

        Args:
            query: Search term for model name/ID
            provider: Filter by provider type
            supports_vision: Filter by vision support
            supports_files: Filter by file/PDF support
            tier: Filter by tier (high, efficient, budget, free)
            limit: Max results

        Returns:
            Filtered list of models
        """
        await self.ensure_loaded()

        results = []

        # Get models from specified provider or all
        if provider:
            models = await self.get_models_for_provider(provider)
        else:
            # Aggregate from main providers
            models = []
            for p in ["openai", "google", "anthropic", "openrouter"]:
                models.extend(await self.get_models_for_provider(p))

        query_lower = query.lower()

        for model in models:
            # Apply filters
            if query_lower and query_lower not in model["id"].lower() and query_lower not in model["name"].lower():
                continue
            if supports_vision is not None and model["supports_vision"] != supports_vision:
                continue
            if supports_files is not None and model["supports_files"] != supports_files:
                continue
            if tier and model["tier"] != tier:
                continue

            results.append(model)

            if len(results) >= limit:
                break

        return results

    async def get_model_info(self, provider_type: str, model_id: str) -> dict | None:
        """Get detailed info for a specific model."""
        models = await self.get_models_for_provider(provider_type)
        for model in models:
            if model["id"] == model_id:
                return model
        return None

    def get_cache_status(self) -> dict:
        """Get cache status info."""
        return {
            "loaded": bool(self._cache),
            "loaded_at": self._cache_loaded_at.isoformat() if self._cache_loaded_at else None,
            "providers": len(self._cache) if self._cache else 0,
            "cache_file_exists": MODELS_CACHE_FILE.exists(),
        }


# Convenience functions
async def get_models_for_provider(provider_type: str) -> list[dict]:
    """Get models for a provider (convenience function)."""
    registry = ModelsRegistry.get_instance()
    return await registry.get_models_for_provider(provider_type)


async def refresh_models_cache() -> bool:
    """Refresh the models cache from API."""
    registry = ModelsRegistry.get_instance()
    return await registry.refresh()


async def search_models(**kwargs) -> list[dict]:
    """Search models (convenience function)."""
    registry = ModelsRegistry.get_instance()
    return await registry.search_models(**kwargs)
