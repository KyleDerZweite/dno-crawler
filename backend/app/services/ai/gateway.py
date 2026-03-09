"""
AI Gateway

Main entry point for AI extraction with:
- Multi-provider support (OpenRouter, LiteLLM, Custom)
- Smart fallback on rate limits
- Health tracking
"""

import base64
import io
from pathlib import Path
from typing import Any

import structlog
from openai import RateLimitError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AIProviderConfigModel
from app.services.ai.config_service import AIConfigService
from app.services.ai.providers import PROVIDER_REGISTRY
from app.services.ai.providers.base import BaseProvider

logger = structlog.get_logger()

# File extension to MIME type mapping
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# File extensions for vision mode
VISION_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}

# File extensions for text mode
TEXT_EXTENSIONS = {".html", ".htm", ".txt", ".csv", ".xml"}


class NoProviderAvailableError(Exception):
    """Raised when no AI provider is available."""

    pass


class AIGateway:
    """Main AI extraction gateway.

    Provides unified interface for AI extraction with:
    - Multiple provider support
    - Smart fallback on errors
    - Health tracking
    """

    def __init__(self, db: AsyncSession):
        """Initialize gateway with database session.

        Args:
            db: Async database session for config access
        """
        self.db = db
        self.config_service = AIConfigService(db)

    def _create_provider(self, config: AIProviderConfigModel) -> BaseProvider:
        """Create provider instance from config.

        Args:
            config: Provider configuration

        Returns:
            Provider instance

        Raises:
            ValueError: If provider type is unknown
        """
        provider_class = PROVIDER_REGISTRY.get(config.provider_type)
        if not provider_class:
            raise ValueError(f"Unknown provider type: {config.provider_type}")

        return provider_class(config)

    async def get_sorted_configs(
        self,
        needs_vision: bool = False,
        needs_files: bool = False,
    ) -> list[AIProviderConfigModel]:
        """Get sorted list of configs for fallback.

        Sorting order:
        1. By user priority
        2. Healthy providers first

        Args:
            needs_vision: Filter to providers supporting vision
            needs_files: Filter to providers supporting files

        Returns:
            Sorted list of provider configs
        """
        configs = await self.config_service.list_enabled()

        # Filter by capability
        filtered = []
        for config in configs:
            if needs_vision and not config.supports_vision:
                continue
            if needs_files and not config.supports_files:
                continue
            filtered.append(config)

        # Sort: by priority, then by health
        return sorted(
            filtered,
            key=lambda c: (
                c.priority,  # By user priority
                0 if c.is_healthy else 1,  # Healthy first
            ),
        )

    async def extract(
        self,
        file_path: Path,
        prompt: str,
    ) -> dict[str, Any]:
        """Extract structured data from a file.

        Automatically detects file type and uses appropriate mode.
        Falls back to next provider on rate limits.

        Args:
            file_path: Path to file (HTML, PDF, or image)
            prompt: Extraction prompt with expected JSON schema

        Returns:
            Parsed JSON response from the model

        Raises:
            NoProviderAvailableError: If no provider is configured or all fail
        """
        suffix = file_path.suffix.lower()
        needs_vision = suffix in VISION_EXTENSIONS
        needs_files = suffix == ".pdf"  # PDFs need file support

        configs = await self.get_sorted_configs(
            needs_vision=needs_vision,
            needs_files=needs_files,
        )

        if not configs:
            raise NoProviderAvailableError(
                "No AI providers configured. Add a provider in Admin → AI Configuration."
            )

        last_error = None

        # For PDFs, strip irrelevant pages before sending to AI
        pdf_bytes = None
        if suffix == ".pdf":
            pdf_bytes = self._strip_pdf_pages(file_path)

        for config in configs:
            try:
                provider = self._create_provider(config)

                if suffix in TEXT_EXTENSIONS:
                    # Text mode
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    result = await provider.extract_text(content, prompt)
                else:
                    # Vision mode — use stripped PDF if available
                    raw = pdf_bytes if pdf_bytes is not None else file_path.read_bytes()
                    image_data = base64.b64encode(raw).decode()
                    mime_type = MIME_TYPES.get(suffix, "application/octet-stream")
                    result = await provider.extract_vision(image_data, mime_type, prompt)

                # Mark success
                tokens = result.get("_extraction_meta", {}).get("usage", {}).get("total_tokens", 0)
                await self.config_service.mark_success(config.id, tokens)
                await self.db.commit()

                return result

            except RateLimitError as e:
                logger.warning(
                    "ai_rate_limited",
                    provider=config.provider_type,
                    model=config.model,
                    error=str(e),
                )
                # Extract retry-after if available
                retry_after = 60  # Default
                if hasattr(e, "headers") and e.headers:
                    retry_after = int(e.headers.get("retry-after", 60))

                await self.config_service.mark_rate_limited(config.id, retry_after)
                await self.db.commit()
                last_error = e
                continue

            except Exception as e:
                logger.error(
                    "ai_extraction_error",
                    provider=config.provider_type,
                    model=config.model,
                    error=str(e),
                )
                await self.config_service.mark_failure(config.id, str(e))
                await self.db.commit()
                last_error = e
                continue

        raise NoProviderAvailableError(f"All providers failed. Last error: {last_error}")

    @staticmethod
    def _strip_pdf_pages(file_path: Path) -> bytes | None:
        """Keep only PDF pages that contain data-relevant keywords.

        Returns stripped PDF bytes, or None if stripping failed or all pages
        are relevant (in which case the caller should use the original file).
        """
        KEYWORDS = [
            "netzentgelt",
            "entgelt",
            "preisblatt",
            "leistungspreis",
            "arbeitspreis",
            "hochlastzeitfenster",
            "hochlastzeit",
            "hochlast",
            "netznutzung",
            "mittelspannung",
            "niederspannung",
            "hochspannung",
            "umspannung",
        ]
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            total = len(doc)
            if total <= 2:
                doc.close()
                return None  # Not worth stripping small PDFs

            keep: list[int] = []
            for i in range(total):
                text = (doc[i].get_text() or "").lower()
                if any(kw in text for kw in KEYWORDS):
                    keep.append(i)

            if not keep or len(keep) == total:
                doc.close()
                return None  # All or no pages match — use original

            # Build stripped PDF
            remove = [i for i in range(total) if i not in keep]
            doc.delete_pages(remove)

            buf = io.BytesIO()
            doc.save(buf, garbage=4, deflate=True)
            doc.close()

            stripped = buf.getvalue()
            logger.info(
                "pdf_pages_stripped",
                file=file_path.name,
                original_pages=total,
                kept_pages=len(keep),
                original_kb=file_path.stat().st_size // 1024,
                stripped_kb=len(stripped) // 1024,
            )
            return stripped

        except ImportError:
            return None  # PyMuPDF not installed
        except Exception as e:
            logger.debug("pdf_strip_failed", file=file_path.name, error=str(e))
            return None

    async def extract_text(
        self,
        content: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Extract structured data from text content directly.

        Args:
            content: Text content (HTML, etc.)
            prompt: Extraction prompt

        Returns:
            Parsed JSON response
        """
        configs = await self.get_sorted_configs()

        if not configs:
            raise NoProviderAvailableError(
                "No AI providers configured. Add a provider in Admin → AI Configuration."
            )

        last_error = None

        for config in configs:
            try:
                provider = self._create_provider(config)
                result = await provider.extract_text(content, prompt)

                tokens = result.get("_extraction_meta", {}).get("usage", {}).get("total_tokens", 0)
                await self.config_service.mark_success(config.id, tokens)
                await self.db.commit()

                return result

            except RateLimitError as e:
                retry_after = 60
                if hasattr(e, "headers") and e.headers:
                    retry_after = int(e.headers.get("retry-after", 60))
                await self.config_service.mark_rate_limited(config.id, retry_after)
                await self.db.commit()
                last_error = e
                continue

            except Exception as e:
                await self.config_service.mark_failure(config.id, str(e))
                await self.db.commit()
                last_error = e
                continue

        raise NoProviderAvailableError(f"All providers failed. Last error: {last_error}")

    async def ocr_pdf(self, file_path: Path, prompt: str) -> str | None:
        """OCR a scanned PDF using vision AI, returning plain text.

        Unlike extract() which expects JSON, this returns raw text from the
        model — useful for transcribing scanned documents before classification.

        Args:
            file_path: Path to the PDF file
            prompt: Instruction for what to transcribe

        Returns:
            Transcribed text, or None if no provider available
        """
        configs = await self.get_sorted_configs(needs_vision=True, needs_files=True)
        if not configs:
            return None

        raw = self._strip_pdf_pages(file_path) or file_path.read_bytes()
        image_data = base64.b64encode(raw).decode()
        last_error = None

        for config in configs:
            try:
                provider = self._create_provider(config)
                text = await provider.extract_plain_text(
                    image_data=image_data,
                    mime_type="application/pdf",
                    prompt=prompt,
                )
                tokens = 0

                await self.config_service.mark_success(config.id, tokens)
                await self.db.commit()

                logger.info(
                    "ocr_pdf_success",
                    model=config.model,
                    text_len=len(text),
                    tokens=tokens,
                )
                return text

            except RateLimitError as e:
                retry_after = 60
                if hasattr(e, "headers") and e.headers:
                    retry_after = int(e.headers.get("retry-after", 60))
                await self.config_service.mark_rate_limited(config.id, retry_after)
                await self.db.commit()
                last_error = e
                continue

            except Exception as e:
                logger.warning(
                    "ocr_pdf_error",
                    provider=config.provider_type,
                    model=config.model,
                    error=str(e),
                )
                await self.config_service.mark_failure(config.id, str(e))
                await self.db.commit()
                last_error = e
                continue

        logger.warning("ocr_pdf_all_providers_failed", last_error=str(last_error))
        return None

    async def test_provider(self, config_id: int) -> dict[str, Any]:
        """Test a provider configuration.

        Args:
            config_id: ID of the config to test

        Returns:
            Test result with status and details
        """
        config = await self.config_service.get_by_id(config_id)
        if not config:
            return {"success": False, "error": "Configuration not found"}

        try:
            provider = self._create_provider(config)
            is_healthy = await provider.health_check()

            if is_healthy:
                await self.config_service.mark_success(config_id)
                await self.db.commit()
                return {
                    "success": True,
                    "provider": config.provider_type,
                    "model": config.model,
                    "message": "Connection successful",
                }
            else:
                return {
                    "success": False,
                    "provider": config.provider_type,
                    "model": config.model,
                    "error": "Health check failed",
                }

        except Exception as e:
            await self.config_service.mark_failure(config_id, str(e))
            await self.db.commit()
            return {
                "success": False,
                "provider": config.provider_type,
                "model": config.model,
                "error": str(e),
            }


async def get_ai_gateway(db: AsyncSession) -> AIGateway:
    """Get AI gateway instance.

    Args:
        db: Database session

    Returns:
        AIGateway instance
    """
    return AIGateway(db)


async def ai_enabled(db: AsyncSession) -> bool:
    """Check if AI extraction is enabled (any provider configured).

    Args:
        db: Database session

    Returns:
        True if at least one enabled provider exists
    """
    service = AIConfigService(db)
    configs = await service.list_enabled()
    return len(configs) > 0
