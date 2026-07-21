from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "sqlite+aiosqlite:///./restaurant_bot.db"

    # LLM
    llm_provider: Literal["anthropic", "openai", "google", "groq"] = "anthropic"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    llm_base_url: str | None = None  # Custom base URL (for Groq, local models, etc.)

    # Auth
    secret_key: str = secrets.token_urlsafe(32)
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Session
    session_store: Literal["memory", "redis", "database"] = "memory"
    redis_url: str | None = None

    # Server
    log_level: str = "INFO"
    cors_origins: list[str] = ["*"]

    # Defaults
    default_currency: str = "USD"
    default_timezone: str = "UTC"


settings = Settings()
