"""
Supply Chain Orchestrator — Central Configuration

Loads environment variables via pydantic-settings and exposes
a typed `Settings` singleton used across all modules.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings sourced from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── PostgreSQL ──────────────────────────────────────────────
    database_url: str = "postgresql://postgres:password@localhost:5432/supply_chain"

    # ── Google Gemini API ───────────────────────────────────────
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # ── GitHub Models (Azure-compatible) ────────────────────────
    github_token: str = ""
    github_models_endpoint: str = "https://models.inference.ai.azure.com"
    github_model: str = "gpt-4o-mini"

    # ── Application ─────────────────────────────────────────────
    log_level: str = "INFO"
    environment: str = "development"

    # ── Connection Pool ─────────────────────────────────────────
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    return Settings()
