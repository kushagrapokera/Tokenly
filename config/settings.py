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
    app_version: str = "1.0.0"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    database_path: Path = Path("data/tokenly.db")
    default_timezone: str = "UTC"

    # The API is a local-only service and the dashboard is served by it from the same
    # origin, so cross-origin access is denied by default. Setting this to a list of
    # origins is only needed when a separate page (a static mockup, a dev server) has
    # to read the API; leaving it empty means no other origin can read usage data.
    cors_allow_origins: list[str] = []
    cors_allow_methods: list[str] = ["GET"]
    cors_allow_headers: list[str] = ["Content-Type"]

    opencode_data_dir: Path | None = None
    opencode_command: str = "opencode"
    opencode_command_timeout_seconds: float = 15.0

    cline_data_dir: Path | None = None

    claude_data_dir: Path | None = None

    # Codex CLI keeps its rollouts under `$CODEX_HOME/sessions/**` (`CODEX_HOME`
    # defaults to `~/.codex`). Set this to point the collector elsewhere.
    codex_home: Path | None = None

    # How far back an incremental scan re-reads, in milliseconds. Re-reading a window
    # costs a few redundant upserts and recovers usage that landed after the last scan.
    rescan_overlap_ms: int = 300_000

    # Whether the server collects on its own. Startup imports whatever history already
    # exists; the interval keeps the dashboard current while the user works. Turning
    # this off leaves collection to the manual rescan endpoint only.
    sync_enabled: bool = True
    sync_interval_seconds: float = 300.0

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL pointing at this settings' SQLite file."""
        return f"sqlite:///{self.database_path.resolve()}"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance, built once and reused."""
    return Settings()
