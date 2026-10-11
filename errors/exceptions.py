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


class AggregationError(TokenlyError):
    """Raised when usage aggregation cannot be computed."""


class InvalidTimezoneError(AggregationError):
    """Raised when a user-selected timezone name is not recognised."""

    def __init__(self, timezone_name: str) -> None:
        super().__init__(f"unknown timezone {timezone_name!r}")
        self.timezone_name = timezone_name


class InvalidTimeRangeError(AggregationError):
    """Raised when a custom date range is empty, inverted, or missing its bounds."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"invalid time range: {detail}")


class InvalidGranularityError(AggregationError):
    """Raised when a timeline granularity is not day, month, or year."""

    def __init__(self, granularity: str) -> None:
        super().__init__(
            f"unsupported timeline granularity {granularity!r}; use 'day', 'month', or 'year'"
        )
        self.granularity = granularity


class UnknownRangeError(AggregationError):
    """Raised when a requested aggregation range is not one of the named ranges."""

    def __init__(self, range_name: str, supported: tuple[str, ...]) -> None:
        super().__init__(f"unknown range {range_name!r}; use one of {', '.join(supported)}")
        self.range_name = range_name
        self.supported = supported


class ApiError(TokenlyError):
    """Raised when a request cannot be served, carrying the status the client should see."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class RequestValidationError(ApiError):
    """Raised when request parameters are missing, malformed, or contradictory."""

    def __init__(self, detail: str) -> None:
        super().__init__(400, detail)


class NotFoundError(ApiError):
    """Raised when the requested resource does not exist."""

    def __init__(self, detail: str) -> None:
        super().__init__(404, detail)


class ServiceUnavailableError(ApiError):
    """Raised when a dependency the request needs is not available right now."""

    def __init__(self, detail: str) -> None:
        super().__init__(503, detail)
