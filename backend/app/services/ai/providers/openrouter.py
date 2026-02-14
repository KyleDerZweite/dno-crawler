"""
OpenRouter Provider

Primary AI provider using native OpenRouter SDK with:
- Dynamic model fetching with modality filtering
- Unified reasoning tokens (effort or max_tokens)
- Async context manager for proper resource cleanup
"""

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
                    models.append(
                        {
                            "id": m["id"],
                            "name": m.get("name", m["id"]),
                            "supports_vision": True,
                            "supports_files": "file" in input_mods,
                        }
                    )

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

        OpenRouter uses a unified 'reasoning' parameter that supports:
        - effort: "xhigh" | "high" | "medium" | "low" | "minimal" | "none"
        - max_tokens: direct token budget (alternative to effort)

        See: https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
        """
        return {
            "method": "level",  # Use effort levels (simpler for users)
            "levels": ["none", "minimal", "low", "medium", "high", "xhigh"],
            "default_level": "medium",
            # These are used when building the API request
            "param_name": "reasoning",  # The parameter name in API request
            "param_format": {
                "effort": "{level}",  # "reasoning": {"effort": "high"}
            },
        }

    @classmethod
    def get_provider_info(cls) -> dict[str, Any]:
        """Return OpenRouter provider display info."""
        return {
            "name": "OpenRouter",
            "description": "Recommended - Access 100+ models with unified API",
            "color": "bg-purple-500/20 text-purple-500",
            # Official OpenRouter logo
            "icon_svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3.10913 12.07C3.65512 12.07 5.76627 11.5988 6.85825 10.98C7.95023 10.3612 7.95023 10.3612 10.207 8.75965C13.0642 6.73196 15.0845 7.41088 18.3968 7.41088" fill="currentColor"/><path d="M3.10913 12.07C3.65512 12.07 5.76627 11.5988 6.85825 10.98C7.95023 10.3612 7.95023 10.3612 10.207 8.75965C13.0642 6.73196 15.0845 7.41088 18.3968 7.41088" stroke="currentColor" stroke-width="3.27593"/><path d="M21.6 7.43108L16.0037 10.6622V4.20001L21.6 7.43108Z" fill="currentColor" stroke="currentColor" stroke-width="0.0363992"/><path d="M3 12.072C3.54599 12.072 5.65714 12.5432 6.74912 13.162C7.8411 13.7808 7.8411 13.7808 10.0978 15.3823C12.9551 17.41 14.9753 16.7311 18.2877 16.7311" fill="currentColor"/><path d="M3 12.072C3.54599 12.072 5.65714 12.5432 6.74912 13.162C7.8411 13.7808 7.8411 13.7808 10.0978 15.3823C12.9551 17.41 14.9753 16.7311 18.2877 16.7311" stroke="currentColor" stroke-width="3.27593"/><path d="M21.4909 16.7109L15.8945 13.4798V19.942L21.4909 16.7109Z" fill="currentColor" stroke="currentColor" stroke-width="0.0363992"/></svg>""",
        }

    # -------------------------------------------------------------------------
    # Instance Methods
    # -------------------------------------------------------------------------

    def _build_reasoning_config(self) -> dict[str, Any] | None:
        """Build OpenRouter unified reasoning config from model_parameters.

        OpenRouter uses:
        - reasoning.effort: "none" | "minimal" | "low" | "medium" | "high" | "xhigh"
        - reasoning.max_tokens: int (alternative to effort)
        - reasoning.exclude: bool (hide reasoning from response)

        See: https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
        """
        params = self.config.model_parameters or {}

        # Check for reasoning_level (effort-based)
        if params.get("reasoning_level"):
            level = params["reasoning_level"]
            if level == "none":
                return None  # Disabled
            return {"effort": level}

        # Check for reasoning_budget (token-based)
        if params.get("reasoning_budget"):
            budget = int(params["reasoning_budget"])
            if budget <= 0:
                return None  # Disabled
            return {"max_tokens": budget}

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
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                        },
                    ],
                }
            ],
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
