"""
OpenRouter Provider

Primary AI provider using native OpenRouter SDK with:
- Dynamic model fetching with modality filtering
- Unified reasoning tokens (effort or max_tokens)
- Async context manager for proper resource cleanup
"""

import json
from typing import Any

import httpx
import structlog
from openrouter import OpenRouter

from app.db import AIProviderConfigModel
from app.services.ai.providers.base import BaseProvider

logger = structlog.get_logger()


class OpenRouterProvider(BaseProvider):
    """OpenRouter provider using native SDK with reasoning token support."""
    
    DEFAULT_MODEL = "google/gemini-2.5-flash-lite-preview-09-2025"
    API_URL = "https://openrouter.ai/api/v1"
    MODELS_ENDPOINT = "https://openrouter.ai/api/v1/models"
    
    def __init__(self, config: AIProviderConfigModel):
        super().__init__(config)
        self._client: OpenRouter | None = None
    
    @property
    def provider_name(self) -> str:
        return "openrouter"
    
    # -------------------------------------------------------------------------
    # Class Methods (no config needed)
    # -------------------------------------------------------------------------
    
    @classmethod
    async def get_available_models(cls) -> list[dict[str, Any]]:
        """Fetch models from public OpenRouter API, filtered by modalities.
        
        Filters for models that support:
        - Input: text + image
        - Output: text
        
        No API key required for this endpoint.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(cls.MODELS_ENDPOINT, timeout=15.0)
                resp.raise_for_status()
                data = resp.json().get("data", [])
            
            models = []
            for m in data:
                arch = m.get("architecture", {})
                input_mods = arch.get("input_modalities", [])
                output_mods = arch.get("output_modalities", [])
                
                # Filter: must support image input AND text output
                if "image" in input_mods and "text" in output_mods:
                    models.append({
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "supports_vision": True,
                        "supports_files": "file" in input_mods,
                    })
            
            logger.info("openrouter_models_fetched", count=len(models))
            return models
            
        except Exception as e:
            logger.warning("openrouter_models_fetch_failed", error=str(e))
            return []
    
    @classmethod
    def get_default_model(cls) -> str:
        return cls.DEFAULT_MODEL
    
    @classmethod
    def get_default_url(cls) -> str | None:
        return cls.API_URL
    
    @classmethod
    def get_reasoning_options(cls) -> dict[str, Any] | None:
        """Return OpenRouter-specific reasoning options.
        
        OpenRouter uses a unified 'reasoning' parameter that supports both
        effort levels and max_tokens budgets.
        """
        return {
            "method": "both",  # Supports both effort levels and token budget
            "levels": ["minimal", "low", "medium", "high", "xhigh"],
            "default_level": "medium",
            "budget_min": 1024,
            "budget_max": 128000,
            "default_budget": 16000,
            "param_name_effort": "reasoning_effort",
            "param_name_tokens": "reasoning_max_tokens",
        }
    
    # -------------------------------------------------------------------------
    # Instance Methods
    # -------------------------------------------------------------------------
    
    def _build_reasoning_config(self) -> dict[str, Any] | None:
        """Build OpenRouter unified reasoning config from model_parameters.
        
        Supports:
        - reasoning_effort: "minimal" | "low" | "medium" | "high" | "xhigh"
        - reasoning_max_tokens: int (direct token budget)
        """
        params = self.config.model_parameters or {}
        
        if params.get("reasoning_effort"):
            return {"effort": params["reasoning_effort"]}
        elif params.get("reasoning_max_tokens"):
            return {"max_tokens": int(params["reasoning_max_tokens"])}
        
        return None
    
    async def extract_text(
        self,
        content: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Extract structured data from text content using OpenRouter SDK."""
        logger.info(
            "openrouter_extract_text_start",
            model=self.model_name,
            content_len=len(content),
        )
        
        full_prompt = f"{prompt}\n\n---\n\nContent to extract from:\n\n{content}"
        reasoning = self._build_reasoning_config()
        
        # Build request kwargs
        request_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": full_prompt}],
            "response_format": {"type": "json_object"},
        }
        
        if reasoning:
            request_kwargs["reasoning"] = reasoning
        
        async with OpenRouter(api_key=self._get_api_key()) as client:
            response = await client.chat.send_async(**request_kwargs)
        
        response_content = response.choices[0].message.content
        result = self._parse_json_response(response_content)
        
        # Extract usage
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        logger.info(
            "openrouter_extract_text_success",
            model=self.model_name,
            records=len(result.get("data", [])),
        )
        
        result["_extraction_meta"] = {
            "raw_response": response_content,
            "mode": "text",
            "provider": self.provider_name,
            "model": self.model_name,
            "usage": usage,
            "reasoning_used": reasoning is not None,
        }
        
        return result
    
    async def extract_vision(
        self,
        image_data: str,
        mime_type: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Extract structured data from image/document using OpenRouter SDK."""
        logger.info(
            "openrouter_extract_vision_start",
            model=self.model_name,
            mime_type=mime_type,
        )
        
        reasoning = self._build_reasoning_config()
        
        request_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_data}"}
                    }
                ]
            }],
            "response_format": {"type": "json_object"},
        }
        
        if reasoning:
            request_kwargs["reasoning"] = reasoning
        
        async with OpenRouter(api_key=self._get_api_key()) as client:
            response = await client.chat.send_async(**request_kwargs)
        
        response_content = response.choices[0].message.content
        result = self._parse_json_response(response_content)
        
        # Extract usage
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        logger.info(
            "openrouter_extract_vision_success",
            model=self.model_name,
            records=len(result.get("data", [])),
        )
        
        result["_extraction_meta"] = {
            "raw_response": response_content,
            "mode": "vision",
            "provider": self.provider_name,
            "model": self.model_name,
            "usage": usage,
            "reasoning_used": reasoning is not None,
        }
        
        return result
    
    async def health_check(self) -> bool:
        """Check if OpenRouter is reachable."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.MODELS_ENDPOINT, timeout=5.0)
                return resp.status_code == 200
        except Exception as e:
            logger.warning("openrouter_health_check_failed", error=str(e))
            return False
