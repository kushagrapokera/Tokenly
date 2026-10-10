"""Dedicated exception definitions for the Tokenly backend."""


class TokenlyError(Exception):
    """Base class for every error Tokenly raises on purpose."""


class ConfigurationError(TokenlyError):
    """Raised when application settings are missing or invalid."""


class DatabaseUnavailableError(TokenlyError):
    """Raised when the SQLite database cannot be reached or queried."""

    def __init__(self, database_url: str, cause: Exception) -> None:
        super().__init__(f"database unavailable for {database_url}: {cause}")
        self.database_url = database_url
        self.__cause__ = cause


class CollectorError(TokenlyError):
    """Raised when a usage collector cannot read its source data."""


class CollectorSourceUnreadableError(CollectorError):
    """Raised when a collector's data source exists but cannot be opened or queried."""

    def __init__(self, source_path: str, cause: Exception) -> None:
        super().__init__(f"cannot read collector source {source_path}: {cause}")
        self.source_path = source_path
        self.__cause__ = cause


class UnsupportedStorageFormatError(CollectorError):
    """Raised when a collector finds its data source in a layout it was not written for."""

    def __init__(self, source_path: str, detail: str) -> None:
        super().__init__(f"unsupported storage format at {source_path}: {detail}")
        self.source_path = source_path
        self.detail = detail
