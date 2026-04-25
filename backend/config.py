from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
    )

    GARMIN_EMAIL: str
    GARMIN_PASSWORD: str
    DATABASE_URL: str = "sqlite:///./db/fitness.db"
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    APP_SITE_URL: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"
    MAX_RETRIES: int = 2
    DEFAULT_MAX_TOKENS: int = 2048


settings = Settings()
