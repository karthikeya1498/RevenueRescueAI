"""Typed environment configuration for the RevenueRescue AI foundation.

Author: Karthikeya
Architectural layer: core configuration.

This module owns configuration loading only. It must not contain business rules,
payment credentials, or workflow behavior.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "RevenueRescue AI"
    app_phase: str = "foundation"
    environment: str = "development"
    log_level: str = "INFO"
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings object used by the application."""

    return Settings()
