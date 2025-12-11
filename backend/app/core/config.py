"""
Zitadel configuration for FastAPI backend.
"""

import os
from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    """Auth configuration loaded from environment variables."""

    zitadel_domain: str = "auth.kylehub.dev"

    @property
    def issuer(self) -> str:
        return f"https://{self.zitadel_domain}"

    @property
    def jwks_url(self) -> str:
        return f"https://{self.zitadel_domain}/.well-known/jwks.json"

    class Config:
        env_prefix = ""
        case_sensitive = False


auth_settings = AuthSettings()
