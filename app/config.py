"""Application configuration and settings."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the prototype services."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    data_directory: Path = Path("data")
    sample_job_file: Path = Path("data/sample_jobs.json")
    resume_storage_directory: Path = Path("data/resumes")
    questionnaire_storage_directory: Path = Path("data/questionnaires")

    evaluation_batch_size: int = 10
    evaluation_similarity_threshold: float = 0.65
    deviation_tolerance: float = 1.0

    application_retry_attempts: int = 3
    application_retry_backoff_seconds: int = 30
    playwright_headless: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    settings = Settings()
    settings.data_directory.mkdir(parents=True, exist_ok=True)
    settings.resume_storage_directory.mkdir(parents=True, exist_ok=True)
    settings.questionnaire_storage_directory.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
