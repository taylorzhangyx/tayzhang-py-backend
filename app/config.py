"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "tayzhang-py-backend"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tayzhang"

    # Content repo path (mounted volume in Docker)
    content_repo_path: str = "/app/content"

    # API Security
    api_key: str = "changeme-in-production"
    api_key_header: str = "X-API-Key"

    # Rate limiting
    rate_limit_per_minute: int = 100

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
