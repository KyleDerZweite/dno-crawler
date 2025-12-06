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

    # Authentication
    jwt_secret: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

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

    # Initial admin user (optional) - provide via .env for local/dev only
    admin_email: str | None = None
    admin_username: str | None = None
    admin_password: str | None = None

    # Storage
    storage_path: str = "./data"
    downloads_path: str = "./data/downloads"
    strategies_path: str = "./data/strategies"

    @field_validator('jwt_secret')
    @classmethod
    def validate_jwt_secret(cls, v: str, info: ValidationInfo) -> str:
        """Validate that jwt_secret is secure for production"""
        if not v or v.strip() == "":
            raise ValueError("jwt_secret cannot be empty")
        
        # Check minimum length
        if len(v) < 32:
            raise ValueError(
                "jwt_secret must be at least 32 characters long for security"
            )
        
        # Production-specific checks (only in production mode)
        debug_mode = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes', 'on')
        if not debug_mode:
            if ("change-me" in v or 
                "development" in v or
                "secret" in v):
                raise ValueError(
                    "jwt_secret must be changed from default value in production. "
                    "Use a secure random string of at least 32 characters."
                )
        
        return v

    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v: PostgresDsn) -> PostgresDsn:
        """Validate database URL"""
        if not v:
            raise ValueError("database_url cannot be empty")
        
        # In Pydantic v2, PostgresDsn is an object, cast to str to check scheme if needed, 
        # but Pydantic already validates scheme for PostgresDsn type.
        return v

    @staticmethod
    def _is_debug_mode() -> bool:
        """Check if we're in debug mode"""
        return os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes', 'on')


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()