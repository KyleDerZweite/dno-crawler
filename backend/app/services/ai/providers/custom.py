"""
Custom Provider

Generic OpenAI-compatible endpoint provider.
Supports any API that implements the OpenAI chat completions format.

Use cases:
- Local Ollama instances
- Self-hosted vLLM servers
- Any OpenAI-compatible API
"""

from typing import Any

import structlog
from openai import AsyncOpenAI

from app.db import AIProviderConfigModel
from app.services.ai.providers.base import BaseProvider

logger = structlog.get_logger()


class CustomProvider(BaseProvider):
    """Generic OpenAI-compatible endpoint provider.

    No special features - just basic chat completions.
    User must know their model ID and endpoint URL.
    """

    MAX_OUTPUT_TOKENS = 4096

    def __init__(self, config: AIProviderConfigModel):
        super().__init__(config)
        self._client: AsyncOpenAI | None = None

    @property
    def provider_name(self) -> str:
        return "custom"

    def _get_client(self) -> AsyncOpenAI:
        """Get or create OpenAI-compatible client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self.config.api_url,
                api_key=self._get_api_key(),
            )
        return self._client

    # -------------------------------------------------------------------------
    # Class Methods
    # -------------------------------------------------------------------------

    @classmethod
    async def get_available_models(cls) -> list[dict[str, Any]]:
        """Return empty list - user must type model ID manually."""
        return []

    @classmethod
    def get_default_model(cls) -> str:
        """No default model for custom endpoints."""
        return ""

    @classmethod
    def get_default_url(cls) -> str | None:
        """No default URL - user must provide."""
        return None

    @classmethod
    def get_reasoning_options(cls) -> dict[str, Any] | None:
        """Custom endpoints have unknown reasoning support."""
        return None

    @classmethod
    def get_provider_info(cls) -> dict[str, Any]:
        """Return Custom provider display info."""
        return {
            "name": "Custom API",
            "description": "Any OpenAI-compatible endpoint (Ollama, vLLM, etc.)",
            "color": "bg-gray-500/20 text-gray-400",
            # Wrench/settings icon
            "icon_svg": """<svg viewBox="0 0 24 24" fill="currentColor"><path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z"/></svg>""",
        }

    # -------------------------------------------------------------------------
    # Instance Methods
    # -------------------------------------------------------------------------

    async def extract_text(
        self,
        content: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Extract structured data from text using OpenAI-compatible API."""
        logger.info(
            "custom_extract_text_start",
            model=self.model_name,
            content_len=len(content),
            api_url=self.config.api_url,
        )

        full_prompt = f"{prompt}\n\n---\n\nContent to extract from:\n\n{content}"

        client = self._get_client()

        response = await client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": full_prompt}],
            response_format={"type": "json_object"},
            max_tokens=self.MAX_OUTPUT_TOKENS,
        )

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
            "custom_extract_text_success",
            model=self.model_name,
            records=len(result.get("data", [])),
        )

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
        """Extract structured data from image using OpenAI-compatible API."""
        logger.info(
            "custom_extract_vision_start",
            model=self.model_name,
            mime_type=mime_type,
            api_url=self.config.api_url,
        )

        client = self._get_client()

        response = await client.chat.completions.create(
            model=self.config.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_data}"}
                    }
                ]
            }],
            response_format={"type": "json_object"},
            max_tokens=self.MAX_OUTPUT_TOKENS,
        )

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
            "custom_extract_vision_success",
            model=self.model_name,
            records=len(result.get("data", [])),
        )

        result["_extraction_meta"] = {
            "raw_response": response_content,
            "mode": "vision",
            "provider": self.provider_name,
            "model": self.model_name,
            "usage": usage,
        }

        return result

    async def health_check(self) -> bool:
        """Check if custom endpoint is reachable."""
        try:
            client = self._get_client()
            await client.models.list()
            return True
        except Exception as e:
            logger.warning(
                "custom_health_check_failed",
                error=str(e),
                api_url=self.config.api_url,
            )
            return False
