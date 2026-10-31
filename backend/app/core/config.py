"""Typed environment configuration for the RevenueRescue AI foundation.

Author: Karthikeya
Architectural layer: core configuration.

This module owns configuration loading only. It must not contain business rules,
payment credentials, or workflow behavior.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "RevenueRescue AI"
    app_phase: str = "foundation"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )
    database_url: str = "sqlite:///./revenuerescue.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    # Security & JWT configuration
    jwt_secret_key: str = "dev-secret-key-change-in-production-only-super-safe-key"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7
    password_min_length: int = 8

    # Payment Gateway Configuration (Defaults to Razorpay Sandbox)
    payment_provider: str = "razorpay"
    payment_provider_mode: Literal["sandbox", "mock", "production"] = "sandbox"
    payment_provider_key_id: str = "rzp_test_placeholder_key_id"
    payment_provider_key_secret: str = "rzp_test_placeholder_secret"
    payment_webhook_secret: str = "rzp_test_webhook_secret"
    payment_provider_base_url: str = "https://api.razorpay.com/v1"
    payment_provider_timeout_seconds: float = 10.0
    payment_simulate_scenarios: bool = True

    # Legacy compatibility fields
    llm_provider: str | None = None
    llm_api_key: str | None = None
    payment_api_key: str | None = None
    razorpay_webhook_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


    @property
    def is_development(self) -> bool:
        """Return True if running in local development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Return True if running in production mode."""
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        """Return True if running in automated test mode."""
        return self.environment == "test"

    def safe_dict(self) -> dict[str, str | int | bool]:
        """Return a sanitized dictionary representation excluding all credentials."""
        return {
            "app_name": self.app_name,
            "app_phase": self.app_phase,
            "environment": self.environment,
            "log_level": self.log_level,
            "server_host": self.server_host,
            "server_port": self.server_port,
            "frontend_origin": self.frontend_origin,
            "database_dialect": self.database_url.split("://")[0] if "://" in self.database_url else "unknown",
            "db_pool_size": self.db_pool_size,
        }


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings object used by the application."""
    return Settings()
