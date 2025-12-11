"""
Core configuration and settings for DNO Crawler.
"""

import os
from functools import lru_cache
from typing import Literal

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

    # External Services
    searxng_url: str = "http://localhost:8888"
    searxng_timeout: int = 30

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

    # Zitadel auth helper properties
    @property
    def zitadel_issuer(self) -> str:
        return f"https://{self.zitadel_domain}"

    @property
    def zitadel_jwks_url(self) -> str:
        return f"https://{self.zitadel_domain}/.well-known/jwks.json"

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
