"""
Google Cloud Code Assist Provider

Uses the Cloud Code Assist API (cloudcode-pa.googleapis.com) with OAuth tokens
from gemini-cli. This is the same API that gemini-cli uses internally.

Benefits:
- Uses Google account's Gemini quota (not API billing)
- Free tier: 60 req/min, 1000 req/day
- Access to Gemini 2.5 Pro with 1M token context
- Works with existing gemini-cli credentials
"""

import json
from typing import Any

import httpx
import structlog

from app.db import AIProviderConfigModel
from app.services.ai.encryption import decrypt_secret
from app.services.ai.interface import AIProviderInterface
from app.services.ai.oauth.google import (
    GEMINI_CODE_ASSIST_ENDPOINT,
    get_credential_manager,
)

logger = structlog.get_logger()

# Headers that gemini-cli sends
CODE_ASSIST_HEADERS = {
    "User-Agent": "google-api-nodejs-client/9.15.1",
    "X-Goog-Api-Client": "gl-node/22.17.0",
    "Client-Metadata": "ideType=IDE_UNSPECIFIED,platform=PLATFORM_UNSPECIFIED,pluginType=GEMINI",
}


class GoogleProvider(AIProviderInterface):
    """Google AI provider using Cloud Code Assist API.

    This uses the same API as gemini-cli, which works with OAuth tokens
    and doesn't require API keys or billing.

    Supports:
    - api_key: Traditional API key (falls back to generativelanguage.googleapis.com)
    - oauth/cli: OAuth credentials from gemini-cli
    """

    MAX_OUTPUT_TOKENS = 8192

    def __init__(self, config: AIProviderConfigModel):
        self.config = config
        self._http_client: httpx.AsyncClient | None = None

    @property
    def provider_name(self) -> str:
        return "google"

    @property
    def model_name(self) -> str:
        return self.config.model

    def _get_api_key(self) -> str | None:
        """Get API key if configured."""
        if self.config.api_key_encrypted:
            return decrypt_secret(self.config.api_key_encrypted)
        return None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=120.0)
        return self._http_client

    async def _get_access_token(self) -> str | None:
        """Get OAuth access token."""
        cred_manager = get_credential_manager()
        return await cred_manager.get_valid_access_token()

    async def _get_or_provision_project(self, access_token: str) -> str:
        """Get or provision a managed project for Cloud Code Assist.

        This is what gemini-cli does - it calls loadCodeAssist to get/create
        a managed project ID.
        """
        # Check cache first
        if hasattr(self, '_cached_project_id') and self._cached_project_id:
            return self._cached_project_id

        client = await self._get_http_client()

        # Call loadCodeAssist to get managed project
        url = f"{GEMINI_CODE_ASSIST_ENDPOINT}/v1internal:loadCodeAssist"

        metadata = {
            "ideType": "IDE_UNSPECIFIED",
            "platform": "PLATFORM_UNSPECIFIED",
            "pluginType": "GEMINI",
        }

        response = await client.post(
            url,
            json={"metadata": metadata},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                **CODE_ASSIST_HEADERS,
            },
        )

        if response.status_code == 200:
            data = response.json()
            project_id = data.get("cloudaicompanionProject")
            if project_id:
                self._cached_project_id = project_id
                logger.info("google_managed_project_found", project_id=project_id)
                return project_id

            # Need to onboard/provision project
            tier_id = data.get("currentTier", {}).get("id") or "FREE"
            return await self._onboard_project(access_token, tier_id)

        logger.warning("google_loadCodeAssist_failed", status=response.status_code)
        raise Exception(f"Failed to get managed project: {response.text[:200]}")

    async def _onboard_project(self, access_token: str, tier_id: str = "FREE") -> str:
        """Onboard user to get a managed project ID."""
        client = await self._get_http_client()

        url = f"{GEMINI_CODE_ASSIST_ENDPOINT}/v1internal:onboardUser"

        metadata = {
            "ideType": "IDE_UNSPECIFIED",
            "platform": "PLATFORM_UNSPECIFIED",
            "pluginType": "GEMINI",
        }

        response = await client.post(
            url,
            json={"tierId": tier_id, "metadata": metadata},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                **CODE_ASSIST_HEADERS,
            },
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("done"):
                project_id = data.get("response", {}).get("cloudaicompanionProject", {}).get("id")
                if project_id:
                    self._cached_project_id = project_id
                    logger.info("google_managed_project_provisioned", project_id=project_id)
                    return project_id

        raise Exception(f"Failed to provision managed project: {response.text[:200]}")

    async def _call_code_assist_api(
        self,
        model: str,
        contents: list[dict],
        generation_config: dict | None = None,
        system_instruction: str | None = None,
    ) -> dict:
        """Call the Cloud Code Assist API (same as gemini-cli).

        This wraps requests in the format expected by cloudcode-pa.googleapis.com.
        """
        access_token = await self._get_access_token()
        if not access_token:
            raise ValueError(
                "No Google OAuth token available. "
                "Please authenticate via Admin panel or run 'gemini auth login'"
            )

        # Get or provision managed project
        project_id = await self._get_or_provision_project(access_token)

        client = await self._get_http_client()

        # Build the request payload in Cloud Code Assist format
        request_payload: dict[str, Any] = {
            "contents": contents,
        }

        if generation_config:
            request_payload["generationConfig"] = generation_config

        if system_instruction:
            request_payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        # Wrap in the Cloud Code Assist format
        wrapped_body = {
            "project": project_id,
            "model": model,
            "request": request_payload,
        }

        url = f"{GEMINI_CODE_ASSIST_ENDPOINT}/v1internal:generateContent"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            **CODE_ASSIST_HEADERS,
        }

        response = await client.post(
            url,
            json=wrapped_body,
            headers=headers,
        )

        if response.status_code != 200:
            error_text = response.text[:500]
            logger.error(
                "google_code_assist_api_error",
                status=response.status_code,
                error=error_text,
            )
            
            if response.status_code == 429:
                from openai import RateLimitError
                # Create a mock response for the error if needed, or just pass message
                raise RateLimitError(
                    message=f"Google Code Assist API rate limit exceeded: {error_text}",
                    response=response,
                    body=response.json() if response.status_code == 429 else None
                )
                
            raise Exception(f"Cloud Code Assist API error: {response.status_code} - {error_text}")

        result = response.json()

        # The response is wrapped in a "response" field
        if "response" in result:
            return result["response"]
        return result

    async def _call_generative_language_api(
        self,
        model: str,
        contents: list[dict],
        generation_config: dict | None = None,
        system_instruction: str | None = None,
    ) -> dict:
        """Call the standard Generative Language API with API key."""
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("No API key configured")

        client = await self._get_http_client()

        request_payload: dict[str, Any] = {
            "contents": contents,
        }

        if generation_config:
            request_payload["generationConfig"] = generation_config

        if system_instruction:
            request_payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        # Use the standard Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        response = await client.post(
            url,
            json=request_payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            error_text = response.text[:500]
            logger.error(
                "google_generative_api_error",
                status=response.status_code,
                error=error_text,
            )
            
            if response.status_code == 429:
                from openai import RateLimitError
                raise RateLimitError(
                    message=f"Google Generative API rate limit exceeded: {error_text}",
                    response=response,
                    body=response.json() if response.status_code == 429 else None
                )

            raise Exception(f"Generative Language API error: {response.status_code} - {error_text}")

        return response.json()

    async def _generate_content(
        self,
        contents: list[dict],
        generation_config: dict | None = None,
        system_instruction: str | None = None,
    ) -> dict:
        """Generate content using the appropriate API."""
        model = self.config.model

        # Prepare generation config if not present
        if generation_config is None:
            generation_config = {}

        # Inject thinking config from model_parameters
        model_params = self.config.model_parameters or {}
        thinking_config = {}

        # Handle Thinking Budget (Gemini 2.5+)
        # -1 = automatic allocation, 0 = disable, > 0 = specific limit
        if "thinking_budget" in model_params:
            budget = model_params["thinking_budget"]
            if budget is not None:
                budget_int = int(budget)
                if budget_int == -1:
                    # Automatic allocation - API docs say omission works, 
                    # but for Code Assist API we must send includeThoughts to get them back
                    thinking_config["includeThoughts"] = True
                elif budget_int > 0:
                    thinking_config["includeThoughts"] = True
                    thinking_config["thinkingBudget"] = budget_int
                elif budget_int == 0:
                    # Explicitly disable
                    thinking_config["includeThoughts"] = False

        # Handle Thinking Level (Gemini 3+)
        if "thinking_level" in model_params:
            level = model_params["thinking_level"]  # low, high
            if level:
                thinking_config["includeThoughts"] = True
                thinking_config["thinkingLevel"] = level.upper()

        # Apply thinking config if set
        if thinking_config:
            generation_config["thinkingConfig"] = thinking_config

        # Prefer OAuth/CLI mode, fall back to API key
        if self.config.auth_type in ("oauth", "cli") or not self._get_api_key():
            return await self._call_code_assist_api(
                model=model,
                contents=contents,
                generation_config=generation_config,
                system_instruction=system_instruction,
            )
        else:
            return await self._call_generative_language_api(
                model=model,
                contents=contents,
                generation_config=generation_config,
                system_instruction=system_instruction,
            )

    async def extract_text(
        self,
        content: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Extract structured data from text using Gemini."""
        logger.info(
            "google_extract_text_start",
            model=self.model_name,
            content_len=len(content),
        )

        system_instruction = "You are a data extraction specialist. Extract the requested information and return ONLY valid JSON, no other text."

        full_prompt = f"""{prompt}

---

Content to extract from:

{content}"""

        contents = [
            {"role": "user", "parts": [{"text": full_prompt}]}
        ]

        generation_config = {
            "responseMimeType": "application/json",
            "maxOutputTokens": self.MAX_OUTPUT_TOKENS,
        }

        response = await self._generate_content(
            contents=contents,
            generation_config=generation_config,
            system_instruction=system_instruction,
        )

        # Extract text from response (extract result text, skipping thoughts)
        response_text = ""
        thoughts = ""
        if "candidates" in response and response["candidates"]:
            candidate = response["candidates"][0]
            if "content" in candidate:
                parts = candidate["content"].get("parts", [])
                for part in parts:
                    if part.get("thought"):
                        thoughts += part.get("text", "") + "\n"
                    elif "text" in part:
                        # This is the actual response text
                        response_text = part["text"]
                        # Usually the result is in the last text part after thoughts

        if not response_text:
            logger.error(
                "google_extraction_empty_response",
                model=self.model_name,
                response_keys=list(response.keys()),
                has_candidates=bool(response.get("candidates")),
            )
            # If we have candidates but no text, might be a safety block
            if "candidates" in response and response["candidates"]:
                candidate = response["candidates"][0]
                if "finishReason" in candidate:
                    logger.warning("google_extraction_finish_reason", reason=candidate["finishReason"])
            
            raise ValueError(f"Google AI returned an empty response (Model: {self.model_name})")

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error("google_extraction_json_parse_error", error=str(e), text=response_text[:500])
            raise ValueError(f"Failed to parse JSON response from Google AI: {str(e)}")

        # Extract usage if available
        usage = None
        if "usageMetadata" in response:
            metadata = response["usageMetadata"]
            usage = {
                "prompt_tokens": metadata.get("promptTokenCount", 0),
                "completion_tokens": metadata.get("candidatesTokenCount", 0),
                "total_tokens": metadata.get("totalTokenCount", 0),
            }

        logger.info(
            "google_extract_text_success",
            model=self.model_name,
            records=len(result.get("data", [])),
        )

        result["_extraction_meta"] = {
            "raw_response": response_text,
            "thoughts": thoughts.strip() if thoughts else None,
            "mode": "text",
            "provider": "google",
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
        """Extract from image/PDF using Gemini's multimodal capability."""
        logger.info(
            "google_extract_vision_start",
            model=self.model_name,
            mime_type=mime_type,
        )

        system_instruction = "You are a data extraction specialist. Extract the requested information and return ONLY valid JSON, no other text."

        # Build multimodal content
        contents = [{
            "role": "user",
            "parts": [
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": image_data,
                    }
                },
                {"text": prompt}
            ]
        }]

        generation_config = {
            "responseMimeType": "application/json",
            "maxOutputTokens": self.MAX_OUTPUT_TOKENS,
        }

        response = await self._generate_content(
            contents=contents,
            generation_config=generation_config,
            system_instruction=system_instruction,
        )

        # Extract text from response (skipping thoughts)
        response_text = ""
        thoughts = ""
        if "candidates" in response and response["candidates"]:
            candidate = response["candidates"][0]
            if "content" in candidate:
                parts = candidate["content"].get("parts", [])
                for part in parts:
                    if part.get("thought"):
                        thoughts += part.get("text", "") + "\n"
                    elif "text" in part:
                        response_text = part["text"]

        if not response_text:
            logger.error(
                "google_extraction_empty_vision_response",
                model=self.model_name,
                response_keys=list(response.keys()),
            )
            raise ValueError(f"Google AI returned an empty response for vision/pdf (Model: {self.model_name})")

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error("google_extraction_vision_json_parse_error", error=str(e), text=response_text[:500])
            raise ValueError(f"Failed to parse JSON response from Google AI: {str(e)}")

        # Extract usage if available
        usage = None
        if "usageMetadata" in response:
            metadata = response["usageMetadata"]
            usage = {
                "prompt_tokens": metadata.get("promptTokenCount", 0),
                "completion_tokens": metadata.get("candidatesTokenCount", 0),
                "total_tokens": metadata.get("totalTokenCount", 0),
            }

        logger.info(
            "google_extract_vision_success",
            model=self.model_name,
            records=len(result.get("data", [])),
        )

        result["_extraction_meta"] = {
            "raw_response": response_text,
            "thoughts": thoughts.strip() if thoughts else None,
            "mode": "vision",
            "mime_type": mime_type,
            "provider": "google",
            "model": self.model_name,
            "usage": usage,
        }

        return result

    async def health_check(self) -> bool:
        """Check if Google AI is accessible."""
        try:
            # Simple test generation
            contents = [{"role": "user", "parts": [{"text": "Hi"}]}]
            await self._generate_content(
                contents=contents,
                generation_config={"maxOutputTokens": 10},
            )
            return True
        except Exception as e:
            logger.warning("google_health_check_failed", error=str(e))
            return False

    @staticmethod
    def is_oauth_available() -> bool:
        """Check if OAuth credentials are available."""
        cred_manager = get_credential_manager()
        return cred_manager.is_authenticated()

    @staticmethod
    def get_oauth_user_info() -> dict | None:
        """Get OAuth user info if authenticated."""
        cred_manager = get_credential_manager()
        return cred_manager.get_user_info()
