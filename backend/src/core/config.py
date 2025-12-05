"""
Core configuration and settings for DNO Crawler.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
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

    # Storage
    storage_path: str = "./data"
    downloads_path: str = "./data/downloads"
    strategies_path: str = "./data/strategies"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
