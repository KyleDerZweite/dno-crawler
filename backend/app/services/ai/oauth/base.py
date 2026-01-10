"""
OAuth Provider Base

Base class for OAuth-based authentication with AI providers.
Will be implemented to support subscription-based access.

TODO: Implement OAuth PKCE flow for browser-based login.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OAuthTokens:
    """OAuth tokens from successful authentication."""
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: str | None = None


class OAuthProviderBase(ABC):
    """Base class for OAuth providers.
    
    Subclasses implement provider-specific OAuth flows.
    """
    
    @abstractmethod
    async def get_auth_url(self, state: str, code_challenge: str) -> str:
        """Generate the OAuth authorization URL.
        
        Args:
            state: Random state for CSRF protection
            code_challenge: PKCE code challenge
            
        Returns:
            URL to redirect user to for authorization
        """
        pass
    
    @abstractmethod
    async def exchange_code(
        self,
        code: str,
        code_verifier: str,
    ) -> OAuthTokens:
        """Exchange authorization code for tokens.
        
        Args:
            code: Authorization code from callback
            code_verifier: PKCE code verifier
            
        Returns:
            OAuth tokens
        """
        pass
    
    @abstractmethod
    async def refresh_tokens(self, refresh_token: str) -> OAuthTokens:
        """Refresh expired access token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            New OAuth tokens
        """
        pass
