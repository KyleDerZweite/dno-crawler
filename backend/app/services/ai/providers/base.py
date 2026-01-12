"""
Base Provider Implementation

Common functionality shared across all provider adapters.
"""

import json
from typing import Any

import structlog
from openai import AsyncOpenAI

from app.db import AIProviderConfigModel
from app.services.ai.encryption import decrypt_secret
from app.services.ai.interface import AIProviderInterface

logger = structlog.get_logger()


class BaseProvider(AIProviderInterface):
    """Base class for OpenAI-compatible providers.

    Most providers (OpenAI, Google AI Studio, Anthropic, OpenRouter)
    support the OpenAI API format, so this base class provides
    common implementation.
    """

    # Maximum tokens to output (prevents runaway generation)
    MAX_OUTPUT_TOKENS = 4096

    def __init__(self, config: AIProviderConfigModel):
        """Initialize provider from config.

        Args:
            config: AI provider configuration from database
        """
        self.config = config
        self._client: AsyncOpenAI | None = None

    @property
    def provider_name(self) -> str:
        return self.config.provider_type

    @property
    def model_name(self) -> str:
        return self.config.model

    def _get_api_key(self) -> str:
        """Get decrypted API key."""
        if self.config.api_key_encrypted:
            return decrypt_secret(self.config.api_key_encrypted)
        # Some providers (like local Ollama) don't need API key
        return "not-required"

    def _get_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self.config.api_url,
                api_key=self._get_api_key(),
                default_headers=self._get_default_headers(),
            )
        return self._client

    def _get_default_headers(self) -> dict[str, str]:
        """Get default headers for requests.

        Override in subclasses for provider-specific headers.
        """
        return {}

    async def extract_text(
        self,
        content: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Extract structured data from text content."""
        logger.info(
            "ai_extract_text_start",
            provider=self.provider_name,
            model=self.model_name,
            content_len=len(content),
        )

        full_prompt = f"{prompt}\n\n---\n\nContent to extract from:\n\n{content}"

        client = self._get_client()

        # Prepare request arguments
        request_kwargs = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": full_prompt}],
            "response_format": {"type": "json_object"},
            "max_tokens": self.MAX_OUTPUT_TOKENS,
        }

        # Inject Thinking Parameters
        model_params = self.config.model_parameters or {}
        extra_body = {}

        # 1. OpenAI Reasoning Effort (mapped from thinking_level)
        if "thinking_level" in model_params:
            # o1/o3 support "reasoning_effort": "low", "medium", "high"
            level = model_params["thinking_level"]
            if level and level in ("low", "medium", "high"):
                request_kwargs["reasoning_effort"] = level

        # 2. Anthropic Thinking (mapped from thinking_budget)
        if "thinking_budget" in model_params:
            budget = model_params["thinking_budget"]
            if budget and int(budget) > 0:
                # Anthropic API expects "thinking": { "type": "enabled", "budget_tokens": ... }
                # Note: When using thinking, standard max_tokens might need to be higher
                extra_body["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": int(budget)
                }

        if extra_body:
            request_kwargs["extra_body"] = extra_body

        response = await client.chat.completions.create(**request_kwargs)

        response_content = response.choices[0].message.content
        result = json.loads(response_content)

        # Extract token usage
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        logger.info(
            "ai_extract_text_success",
            provider=self.provider_name,
            model=self.model_name,
            records=len(result.get("data", [])),
        )

        # Add metadata
        result["_extraction_meta"] = {
            "raw_response": response_content,
            "mode": "text",
            "provider": self.provider_name,
            "model": self.model_name,
            "usage": usage,
        }

        return result

    async def extract_vision(
        self,
        image_data: str,
        mime_type: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Extract structured data from image/document."""
        logger.info(
            "ai_extract_vision_start",
            provider=self.provider_name,
            model=self.model_name,
            mime_type=mime_type,
        )

        client = self._get_client()

        # Prepare request arguments
        request_kwargs = {
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
            "max_tokens": self.MAX_OUTPUT_TOKENS,
        }

        # Inject Thinking Parameters
        model_params = self.config.model_parameters or {}
        extra_body = {}

        # 1. OpenAI Reasoning Effort
        if "thinking_level" in model_params:
            level = model_params["thinking_level"]
            if level and level in ("low", "medium", "high"):
                request_kwargs["reasoning_effort"] = level

        # 2. Anthropic Thinking
        if "thinking_budget" in model_params:
            budget = model_params["thinking_budget"]
            if budget and int(budget) > 0:
                extra_body["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": int(budget)
                }

        if extra_body:
            request_kwargs["extra_body"] = extra_body

        response = await client.chat.completions.create(**request_kwargs)

        response_content = response.choices[0].message.content
        result = json.loads(response_content)

        # Extract token usage
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        logger.info(
            "ai_extract_vision_success",
            provider=self.provider_name,
            model=self.model_name,
            records=len(result.get("data", [])),
        )

        # Add metadata
        result["_extraction_meta"] = {
            "raw_response": response_content,
            "mode": "vision",
            "provider": self.provider_name,
            "model": self.model_name,
            "usage": usage,
        }

        return result

    async def health_check(self) -> bool:
        """Check if provider is reachable."""
        try:
            client = self._get_client()
            # Simple models list call to verify connectivity
            await client.models.list()
            return True
        except Exception as e:
            logger.warning(
                "ai_health_check_failed",
                provider=self.provider_name,
                error=str(e),
            )
            return False
