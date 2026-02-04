"""
Base Provider - Abstract class for all AI extraction providers.

All provider-specific logic (model fetching, extraction, reasoning params)
must be implemented in the respective provider subclass.
"""

import json
from abc import ABC, abstractmethod
from typing import Any

import structlog

from app.db import AIProviderConfigModel
from app.services.ai.encryption import decrypt_secret

logger = structlog.get_logger()


class BaseProvider(ABC):
    """Abstract base class for AI providers.

    Class methods (get_available_models, get_default_model) can be called
    without a config instance - used in the "Add Provider" UI flow.

    Instance methods (extract_text, extract_vision, health_check) require
    a config instance from the database.
    """

    MAX_OUTPUT_TOKENS = 4096

    def __init__(self, config: AIProviderConfigModel):
        """Initialize provider with database config."""
        self.config = config

    def _get_api_key(self) -> str:
        """Get decrypted API key from config."""
        if self.config.api_key_encrypted:
            return decrypt_secret(self.config.api_key_encrypted)
        return "not-required"

    # -------------------------------------------------------------------------
    # Class Methods (no config needed)
    # -------------------------------------------------------------------------

    @classmethod
    @abstractmethod
    async def get_available_models(cls) -> list[dict[str, Any]]:
        """Fetch available models from provider.

        Must be a @classmethod so it can be called before configuration exists.

        Returns:
            List of model dicts with at minimum:
            - id: Model identifier (e.g., "anthropic/claude-3.5-sonnet")
            - name: Display name
        """
        ...

    @classmethod
    @abstractmethod
    def get_default_model(cls) -> str:
        """Return the recommended default model ID."""
        ...

    @classmethod
    @abstractmethod
    def get_default_url(cls) -> str | None:
        """Return the default API URL for this provider, or None if not applicable."""
        ...

    @classmethod
    @abstractmethod
    def get_reasoning_options(cls) -> dict[str, Any] | None:
        """Return reasoning configuration options for this provider.

        Returns None if provider doesn't support reasoning tokens.

        If supported, returns a dict with:
        - method: "level" | "budget" | "both"
        - levels: List of level options (if method is "level" or "both")
        - budget_min: Minimum token budget (if method is "budget" or "both")
        - budget_max: Maximum token budget (if method is "budget" or "both")
        - default_level: Default level value
        - default_budget: Default budget value
        - param_name_effort: Backend parameter name for effort level
        - param_name_tokens: Backend parameter name for token budget
        """
        ...

    @classmethod
    @abstractmethod
    def get_provider_info(cls) -> dict[str, Any]:
        """Return provider display info for the frontend UI.

        Returns a dict with:
        - name: Display name (e.g., "OpenRouter")
        - description: Short description shown in dropdown
        - color: CSS color classes (e.g., "bg-purple-500/20 text-purple-500")
        - icon_svg: Inline SVG string for the logo (or empty string for fallback)
        """
        ...

    # -------------------------------------------------------------------------
    # Instance Methods (require config)
    # -------------------------------------------------------------------------

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name for logging."""
        ...

    @property
    def model_name(self) -> str:
        """Get model name from config."""
        return self.config.model

    @abstractmethod
    async def extract_text(
        self,
        content: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Extract structured data from text content.

        Args:
            content: Text content (HTML, plain text, etc.)
            prompt: Extraction prompt with expected JSON schema

        Returns:
            Parsed JSON response with _extraction_meta included
        """
        ...

    @abstractmethod
    async def extract_vision(
        self,
        image_data: str,
        mime_type: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Extract structured data from image/document.

        Args:
            image_data: Base64-encoded image or document
            mime_type: MIME type (e.g., "image/png", "application/pdf")
            prompt: Extraction prompt with expected JSON schema

        Returns:
            Parsed JSON response with _extraction_meta included
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is reachable and working."""
        ...

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from model response, handling common edge cases."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    return json.loads(content[start:end].strip())
            raise
