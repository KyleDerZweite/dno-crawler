"""
OAuth Package for AI Provider Authentication

Contains OAuth flows for:
- Google (Gemini) - gemini-cli compatible
"""

from app.services.ai.oauth.google import (
    GoogleCredentialManager,
    GoogleOAuthFlow,
    get_credential_manager,
)

__all__ = [
    "GoogleOAuthFlow",
    "GoogleCredentialManager",
    "get_credential_manager",
]
