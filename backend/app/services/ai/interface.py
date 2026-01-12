"""
AI Provider Interface

Abstract base class defining the contract that all AI providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Any


class AIProviderInterface(ABC):
    """Abstract interface for AI providers.

    All provider adapters (OpenAI, Google, Anthropic, OpenRouter, etc.)
    must implement this interface.
    """

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
            Parsed JSON response from the model
        """
        pass

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
            Parsed JSON response from the model
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is reachable and working.

        Returns:
            True if provider is healthy, False otherwise
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name for logging."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the model name being used."""
        pass
