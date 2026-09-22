"""SQLAlchemy column types for AgentFlow SQLite persistence.

UUID values are stored as canonical 36-character strings
(``xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx``). Domain code continues to use
``uuid.UUID``; conversion happens only in this adapter.

Timestamps are stored as ISO-8601 UTC strings ending in ``+00:00``. SQLite's
native datetime affinity does not preserve timezone, so an explicit string
strategy is used for restart-safe round-trips.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import String, TypeDecorator


class UuidAsString(TypeDecorator[UUID]):
    """Persist ``UUID`` as a stable 36-character canonical string."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: UUID | str | None, dialect: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return str(value)
        return str(UUID(str(value)))

    def process_result_value(self, value: str | None, dialect: object) -> UUID | None:
        if value is None:
            return None
        return UUID(str(value))


class UtcDateTimeAsIso(TypeDecorator[datetime]):
    """Persist timezone-aware UTC datetimes as ISO-8601 strings."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: object,
    ) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("persistence timestamps must be timezone-aware UTC")
        return value.astimezone(UTC).isoformat()

    def process_result_value(
        self,
        value: str | datetime | None,
        dialect: object,
    ) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
