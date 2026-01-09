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

import base64
import json
from pathlib import Path
from typing import Any

import structlog
from openai import AsyncOpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from tenacity.wait import wait_base

from app.core.config import settings

logger = structlog.get_logger()


class WaitRateLimit(wait_base):
    """
    Custom wait strategy that honors rate limit info from:
    1. HTTP headers (Retry-After, x-ratelimit-reset-requests)
    2. Error response body (Google's retryDelay in JSON, or "retry in Xs" in message)
    Falls back to exponential backoff if none found.
    """
    def __init__(self, fallback: wait_base):
        self.fallback = fallback

    def __call__(self, retry_state) -> float:
        import re

        exc = retry_state.outcome.exception()

        # We only look for headers if it's a RateLimitError
        if isinstance(exc, RateLimitError):
            # 1. Check HTTP headers first
            headers = getattr(exc, "headers", {})

            # Standard Retry-After (seconds)
            retry_after = headers.get("retry-after")
            if retry_after:
                try:
                    wait_time = float(retry_after) + 1.0
                    logger.info("rate_limit_wait", source="header", seconds=wait_time)
                    return wait_time
                except (ValueError, TypeError):
                    pass

            # OpenAI specific: x-ratelimit-reset-requests
            reset_requests = headers.get("x-ratelimit-reset-requests")
            if reset_requests:
                try:
                    if isinstance(reset_requests, str) and reset_requests.endswith('s'):
                        wait_time = float(reset_requests[:-1]) + 1.0
                    else:
                        wait_time = float(reset_requests) + 1.0
                    logger.info("rate_limit_wait", source="x-ratelimit-header", seconds=wait_time)
                    return wait_time
                except (ValueError, TypeError):
                    pass

            # 2. Parse from error message/body (Google AI Studio / OpenRouter style)
            error_str = str(exc)

            # Look for "retryDelay": "45s" in JSON response
            retry_delay_match = re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s?"', error_str)
            if retry_delay_match:
                wait_time = float(retry_delay_match.group(1)) + 2.0  # 2s buffer for Google
                logger.info("rate_limit_wait", source="retryDelay_json", seconds=wait_time)
                return wait_time

            # Look for "Please retry in 45.5s" or "retry in 45 seconds" patterns
            retry_in_match = re.search(r'retry in (\d+(?:\.\d+)?)\s*s', error_str, re.IGNORECASE)
            if retry_in_match:
                wait_time = float(retry_in_match.group(1)) + 2.0
                logger.info("rate_limit_wait", source="retry_in_message", seconds=wait_time)
                return wait_time

        # Fallback to exponential backoff if no specific info found
        fallback_time = self.fallback(retry_state)
        logger.info("rate_limit_wait", source="exponential_fallback", seconds=fallback_time)
        return fallback_time


class AIExtractor:
    """OpenAI-compatible extractor for vision and text models."""

    # File extensions that should use vision mode
    VISION_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}

    # File extensions that should use text mode
    TEXT_EXTENSIONS = {".html", ".htm", ".txt", ".csv", ".xml"}

    # Maximum tokens to output (prevents runaway generation, safe for structured data)
    MAX_OUTPUT_TOKENS = 2048

    def __init__(self):
        if not settings.ai_enabled:
            raise RuntimeError("AI extraction not configured. Set AI_API_URL and AI_MODEL.")

        self.client = AsyncOpenAI(
            base_url=settings.ai_api_url,
            api_key=settings.ai_api_key or "ollama",  # Ollama needs non-empty string
            default_headers={
                # OpenRouter app identification - shows in dashboard activity
                "HTTP-Referer": "https://github.com/KyleDerZweite/dno-crawler",
                "X-Title": "DNO Crawler",
            }
        )
        self.model = settings.ai_model

    @retry(
        stop=stop_after_attempt(settings.ai_rate_limit_retries),
        wait=WaitRateLimit(
            fallback=wait_exponential(
                multiplier=settings.ai_rate_limit_backoff // 2,
                min=settings.ai_rate_limit_backoff // 2,
                max=settings.ai_rate_limit_backoff * 2
            )
        ),
        retry=retry_if_exception_type((RateLimitError, Exception)),
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
                response_format={"type": "json_object"},
                max_tokens=self.MAX_OUTPUT_TOKENS
            )

            response_content = response.choices[0].message.content
            result = json.loads(response_content)

            # Extract token usage if available
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            logger.info(
                "ai_extract_text_success",
                model=self.model,
                records=len(result.get("data", []))
            )

            # Return enriched result with metadata
            result["_extraction_meta"] = {
                "raw_response": response_content,
                "mode": "text",
                "model": self.model,
                "usage": usage,
            }
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

        was_optimized = False

        # Encode file as base64
        # Perform PDF preprocessing if applicable
        if file_path.suffix.lower() == ".pdf":
            file_bytes, was_optimized = self._preprocess_pdf(file_path, prompt)
            file_data = base64.b64encode(file_bytes).decode()
        else:
            # Standard read for images
            with open(file_path, "rb") as f:
                file_bytes = f.read()
                file_data = base64.b64encode(file_bytes).decode()

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
            # First attempt: use pre-processed file (if applicable)
            result = await self._call_vision_api(prompt, file_data, mime_type)

            # Check for fallback condition:
            # If we used an optimized subset AND the result contains no data -> Retry with full file
            data_found = result.get("data") and len(result.get("data")) > 0

            if was_optimized and not data_found:
                logger.warning("ai_extract_vision_retry",
                             file=file_path.name,
                             reason="subset_yielded_no_data",
                             msg="Retrying with full original file")

                # Load full original file
                with open(file_path, "rb") as f:
                    full_bytes = f.read()
                full_data = base64.b64encode(full_bytes).decode()

                # Retry
                result = await self._call_vision_api(prompt, full_data, mime_type)
            elif was_optimized:
                logger.info("ai_extract_vision_subset_success", file=file_path.name, records=len(result.get("data", [])))

            return result

        except json.JSONDecodeError as e:
            # If JSON fail, we might want to retry too? simpler to just error for now unless it was subset issue.
            logger.error("ai_extract_json_error", error=str(e))
            raise ValueError(f"AI returned invalid JSON: {e}")
        except Exception as e:
            # Try to extract more details if it's an API error
            error_details = str(e)
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_details += f" | Response: {e.response.text}"

            logger.error("ai_extract_vision_error", error=error_details)
            raise

    async def _call_vision_api(self, prompt: str, base64_data: str, mime_type: str) -> dict[str, Any]:
        """Helper to make the actual API call."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{base64_data}"}
                    }
                ]
            }],
            response_format={"type": "json_object"},
            max_tokens=self.MAX_OUTPUT_TOKENS
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        # Extract token usage if available
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        logger.info(
            "ai_extract_vision_success",
            model=self.model,
            records=len(result.get("data", []))
        )

        # Return enriched result with metadata
        result["_extraction_meta"] = {
            "raw_response": content,
            "mode": "vision",
            "model": self.model,
            "usage": usage,
        }
        return result

    def _preprocess_pdf(self, file_path: Path, prompt: str) -> tuple[bytes, bool]:
        """
        Pre-filter PDF pages based on keywords in the prompt to reduce payload size.
        
        Args:
            file_path: Path to the PDF file
            prompt: The extraction prompt (used to determine keywords)
            
        Returns:
            Tuple of (file_bytes, was_optimized)
        """
        try:
            import fitz  # PyMuPDF

            # Determine keywords based on prompt
            keywords = []
            exclude_keywords = []
            prompt_lower = prompt.lower()
            if "netzentgelte" in prompt_lower:
                # Use stricter keywords to avoid keeping pages with just generic terms like "Strom" or "Netz"
                # "KA-Sätze" (Konzessionsabgaben) pages often get kept because of generic terms.
                keywords = ["preisblatt", "leistungspreis", "arbeitspreis", "netzentgelte", "entnahme", "ebenenspezifisch"]
                exclude_keywords = ["konzession", "ka-sätze"]
            elif "hlzf" in prompt_lower or "hochlast" in prompt_lower:
                keywords = ["hochlast", "zeitfenster", "hlzf", "zeitscheiben", "lastgang"]

            if not keywords:
                # No specific context detected, return original
                with open(file_path, "rb") as f:
                    return f.read(), False

            doc = fitz.open(file_path)
            relevant_pages = []
            has_text_content = False

            for page_num, page in enumerate(doc):
                text = page.get_text().lower()

                # If page has significant text, mark that we aren't dealing with pure images
                if len(text.strip()) > 50:
                    has_text_content = True

                # Check for exclude keywords
                if exclude_keywords and any(k in text for k in exclude_keywords):
                    continue

                # Check for keywords
                if any(k in text for k in keywords):
                    relevant_pages.append(page_num)

            # Decision logic:
            if not has_text_content:
                logger.info("pdf_pre_filter_skipped", reason="scanned_document", file=file_path.name)
                with open(file_path, "rb") as f:
                    return f.read(), False

            if not relevant_pages:
                logger.info("pdf_pre_filter_skipped", reason="no_keywords_found", file=file_path.name)
                with open(file_path, "rb") as f:
                    return f.read(), False

            # Create new PDF with only relevant pages
            logger.info("pdf_pre_filter_success",
                       original_pages=len(doc),
                       kept_pages=len(relevant_pages),
                       file=file_path.name)

            out_doc = fitz.open()

            for p_idx in relevant_pages:
                out_doc.insert_pdf(doc, from_page=p_idx, to_page=p_idx)

            # Use compression to minimize size
            return out_doc.tobytes(garbage=4, deflate=True), True

        except ImportError:
            logger.warning("pymupdf_not_installed", msg="Skipping PDF optimization")
            with open(file_path, "rb") as f:
                return f.read(), False
        except Exception as e:
            logger.error("pdf_pre_filter_failed", error=str(e))
            # Fallback to original
            with open(file_path, "rb") as f:
                return f.read(), False


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

