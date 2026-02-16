"""
Core configuration and settings for DNO Crawler.
"""

import json
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "DNO Crawler"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://localhost:3000"])

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://dno_user:password@localhost:5432/dno_crawler"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10
    use_alembic_migrations: bool = Field(
        default=False,
        validation_alias="USE_ALEMBIC_MIGRATIONS",
        description="If True, skip create_all() and rely on Alembic migrations",
    )

    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    redis_password: str | None = None

    # Authentication
    zitadel_domain: str = Field(default="auth.example.com", validation_alias="ZITADEL_DOMAIN")
    zitadel_client_id: str | None = Field(default=None, validation_alias="ZITADEL_CLIENT_ID")

    # Rate Limiting
    rate_limit_public: int = 10  # requests per minute for unauthenticated
    rate_limit_authenticated: int = 100  # requests per minute for authenticated
    trusted_proxy_count: int = Field(default=1, validation_alias="TRUSTED_PROXY_COUNT")

    # Note: AI configuration has been moved to database.
    # Configure AI providers via Admin UI → AI Configuration.
    # Legacy env vars (AI_API_URL, AI_API_KEY, AI_MODEL) are no longer used.

    # Crawler Politeness
    contact_email: str = Field(default="", validation_alias="CONTACT_EMAIL")

    @property
    def has_contact_email(self) -> bool:
        """Check if a valid contact email is configured."""
        return bool(self.contact_email)

    # Crawler
    crawler_max_concurrent: int = 5
    crawler_request_delay: float = 1.0  # seconds between requests
    crawler_timeout: int = 30
    crawler_user_agent: str = (
        "Mozilla/5.0 (compatible; DNOCrawler/1.0; +https://github.com/KyleDerZweite/dno-crawler)"
    )

    # AI (Optional Auto-Config)
    openrouter_key: str | None = Field(default=None, validation_alias="OPENROUTER_KEY")

    # Storage (STORAGE_PATH env var maps to storage_path)
    storage_path: str = Field(default="/data", validation_alias="STORAGE_PATH")

    # Rate Limiting for DDGS Search
    ddgs_request_delay_seconds: int = 5  # Hard cap: wait 5s between searches
    ddgs_batch_delay_seconds: int = 8  # Delay between DNOs in batch mode
    ddgs_rate_limit_cooldown: int = 60  # Cooldown if we hit rate limit (429/418)
    ddgs_timeout: int = 20  # Timeout for DDGS requests

    # Computed storage paths
    @property
    def downloads_path(self) -> str:
        """Path to downloaded files, derived from storage_path."""
        from pathlib import Path

        return str(Path(self.storage_path) / "downloads")

    # Zitadel auth helper properties
    @property
    def zitadel_issuer(self) -> str:
        return f"https://{self.zitadel_domain}"

    @property
    def is_auth_enabled(self) -> bool:
        """Determine if auth is enabled based on Zitadel domain."""
        return bool(self.zitadel_domain) and self.zitadel_domain != "auth.example.com"

    @property
    def is_production(self) -> bool:
        """Check if running in production or staging environment."""
        return self.environment in ("production", "staging")

    @property
    def zitadel_jwks_url(self) -> str:
        return f"https://{self.zitadel_domain}/oauth/v2/keys"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from JSON string if needed."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # If not valid JSON, treat as comma-separated
                return [s.strip() for s in v.split(",")]
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: PostgresDsn) -> PostgresDsn:
        """Validate database URL"""
        if not v:
            raise ValueError("database_url cannot be empty")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()


# Backwards compatibility alias for auth module
class AuthSettings:
    """Auth settings wrapper for backwards compatibility."""

    @property
    def issuer(self) -> str:
        return settings.zitadel_issuer

    @property
    def jwks_url(self) -> str:
        return settings.zitadel_jwks_url


auth_settings = AuthSettings()
