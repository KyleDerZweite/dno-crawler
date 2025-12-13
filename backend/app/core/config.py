"""
Core configuration and settings for DNO Crawler.
"""

import json
import os
from functools import lru_cache
from typing import Literal, Any

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, ValidationInfo
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
    environment: Literal["development", "staging", "production"] = "development"
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

    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    redis_password: str | None = None

    # Zitadel Authentication
    zitadel_domain: str = "auth.kylehub.dev"

    # Rate Limiting
    rate_limit_public: int = 10  # requests per minute for unauthenticated
    rate_limit_authenticated: int = 100  # requests per minute for authenticated

    # Ollama (LLM)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_vision_model: str = "llava"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout: int = 120

    # Crawler
    crawler_max_concurrent: int = 5
    crawler_request_delay: float = 1.0  # seconds between requests
    crawler_timeout: int = 30
    crawler_user_agent: str = (
        "Mozilla/5.0 (compatible; DNOCrawler/1.0; +https://github.com/KyleDerZweite/dno-crawler)"
    )

    # Storage
    storage_path: str = "./data"
    downloads_path: str = "./data/downloads"

    # Rate Limiting for DDGS Search
    ddgs_request_delay_seconds: int = 5  # Hard cap: wait 5s between searches
    ddgs_batch_delay_seconds: int = 8    # Delay between DNOs in batch mode
    ddgs_rate_limit_cooldown: int = 60   # Cooldown if we hit rate limit (429/418)
    ddgs_timeout: int = 20               # Timeout for DDGS requests

    # LLM Models
    ollama_fast_model: str = "ministral:3b"  # For text parsing (DNO name extraction)

    # Zitadel auth helper properties
    @property
    def zitadel_issuer(self) -> str:
        return f"https://{self.zitadel_domain}"

    @property
    def zitadel_jwks_url(self) -> str:
        return f"https://{self.zitadel_domain}/oauth/v2/keys"

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from JSON string if needed."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # If not valid JSON, treat as comma-separated
                return [s.strip() for s in v.split(',')]
        return v

    @field_validator('database_url')
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
