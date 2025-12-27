"""
AI Extractor Service

OpenAI-compatible API client for AI-based data extraction.
Supports any provider with OpenAI-compatible API format:
- Google AI Studio (Gemini)
- OpenRouter
- Ollama (local)

Modes:
- TEXT mode: For HTML files - pass content as text (cheaper, faster)
- VISION mode: For PDF/images - encode as base64 image

All env vars optional - returns None if AI not configured.
"""

import json
import base64
import asyncio
from pathlib import Path
from typing import Any

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

logger = structlog.get_logger()


class AIExtractor:
    """OpenAI-compatible extractor for vision and text models."""
    
    # File extensions that should use vision mode
    VISION_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
    
    # File extensions that should use text mode
    TEXT_EXTENSIONS = {".html", ".htm", ".txt", ".csv", ".xml"}
    
    def __init__(self):
        if not settings.ai_enabled:
            raise RuntimeError("AI extraction not configured. Set AI_API_URL and AI_MODEL.")
        
        self.client = AsyncOpenAI(
            base_url=settings.ai_api_url,
            api_key=settings.ai_api_key or "ollama"  # Ollama needs non-empty string
        )
        self.model = settings.ai_model
    
    @retry(
        stop=stop_after_attempt(settings.ai_rate_limit_retries),
        wait=wait_exponential(
            multiplier=settings.ai_rate_limit_backoff // 2,
            min=settings.ai_rate_limit_backoff // 2,
            max=settings.ai_rate_limit_backoff * 2
        ),
        reraise=True
    )
    async def extract(self, file_path: Path, prompt: str) -> dict[str, Any]:
        """
        Extract structured data from a file using AI.
        
        Automatically selects text or vision mode based on file extension.
        
        Args:
            file_path: Path to file (HTML, PDF, or image)
            prompt: Extraction prompt with expected JSON schema
            
        Returns:
            Parsed JSON response from the model
        """
        suffix = file_path.suffix.lower()
        
        # Route to appropriate extraction method
        if suffix in self.TEXT_EXTENSIONS:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            return await self.extract_text(content, prompt)
        else:
            return await self.extract_vision(file_path, prompt)
    
    async def extract_text(self, content: str, prompt: str) -> dict[str, Any]:
        """
        Extract structured data from text content (HTML, etc).
        
        Uses text-only mode - cheaper and faster than vision.
        
        Args:
            content: Text content (e.g., HTML)
            prompt: Extraction prompt with expected JSON schema
            
        Returns:
            Parsed JSON response from the model
        """
        logger.info("ai_extract_text_start", model=self.model, content_len=len(content))
        
        # Combine prompt with content
        full_prompt = f"{prompt}\n\n---\n\nContent to extract from:\n\n{content}"
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": full_prompt
                }],
                response_format={"type": "json_object"}
            )
            
            response_content = response.choices[0].message.content
            result = json.loads(response_content)
            
            logger.info(
                "ai_extract_text_success",
                model=self.model,
                records=len(result.get("data", []))
            )
            return result
            
        except json.JSONDecodeError as e:
            logger.error("ai_extract_json_error", error=str(e), content=response_content[:500])
            raise ValueError(f"AI returned invalid JSON: {e}")
        except Exception as e:
            logger.error("ai_extract_text_error", error=str(e))
            raise
    
    async def extract_vision(self, file_path: Path, prompt: str) -> dict[str, Any]:
        """
        Extract structured data from a file using AI vision.
        
        Uses base64-encoded image/document for vision models.
        
        Args:
            file_path: Path to PDF or image file
            prompt: Extraction prompt with expected JSON schema
            
        Returns:
            Parsed JSON response from the model
        """
        logger.info("ai_extract_vision_start", file=str(file_path), model=self.model)
        
        # Encode file as base64
        with open(file_path, "rb") as f:
            file_data = base64.b64encode(f.read()).decode()
        
        # Determine MIME type
        suffix = file_path.suffix.lower()
        mime_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(suffix, "application/octet-stream")
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{file_data}"}
                        }
                    ]
                }],
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            logger.info(
                "ai_extract_vision_success",
                model=self.model,
                records=len(result.get("data", []))
            )
            return result
            
        except json.JSONDecodeError as e:
            logger.error("ai_extract_json_error", error=str(e), content=content[:500])
            raise ValueError(f"AI returned invalid JSON: {e}")
        except Exception as e:
            logger.error("ai_extract_vision_error", error=str(e))
            raise


def get_ai_extractor() -> AIExtractor | None:
    """
    Get AI extractor if configured, else None.
    
    Returns:
        AIExtractor instance or None if AI not configured
    """
    if not settings.ai_enabled:
        logger.debug("ai_not_configured", msg="Using regex-only extraction")
        return None
    return AIExtractor()


async def extract_with_ai(
    file_path: str | Path,
    prompt: str
) -> dict[str, Any] | None:
    """
    Convenience function for AI extraction (auto-detects file type).
    
    Args:
        file_path: Path to file (HTML, PDF, or image)
        prompt: Extraction prompt
        
    Returns:
        Extracted data dict, or None if AI not configured
    """
    extractor = get_ai_extractor()
    if extractor is None:
        return None
    return await extractor.extract(Path(file_path), prompt)


async def extract_html_with_ai(
    html_content: str,
    prompt: str
) -> dict[str, Any] | None:
    """
    Convenience function for AI extraction of HTML text content.
    
    Uses text mode (cheaper than vision).
    
    Args:
        html_content: HTML content as string
        prompt: Extraction prompt
        
    Returns:
        Extracted data dict, or None if AI not configured
    """
    extractor = get_ai_extractor()
    if extractor is None:
        return None
    return await extractor.extract_text(html_content, prompt)

