"""Column types SQLite does not provide natively.

SQLite stores datetimes as text and hands them back without a timezone, so a value
written as UTC would return naive and later compare unequal to an aware datetime.
`UtcDateTime` pins every value to UTC on the way in and re-attaches UTC on the way out,
so a timestamp read from the database always equals the one that was written.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """A datetime that is always stored and returned as an aware UTC value."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        """Convert an aware or naive datetime to UTC before it is stored."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        """Re-attach UTC to a value SQLite returned without one."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
