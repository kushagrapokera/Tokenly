"""Application settings loaded from environment variables and an optional .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Tokenly backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Tokenly"
    app_version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    database_path: Path = Path("data/tokenly.db")

    opencode_data_dir: Path | None = None
    opencode_command: str = "opencode"
    opencode_command_timeout_seconds: float = 15.0

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL pointing at this settings' SQLite file."""
        return f"sqlite:///{self.database_path.resolve()}"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance, built once and reused."""
    return Settings()
