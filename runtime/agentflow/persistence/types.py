"""SQLAlchemy column types for AgentFlow SQLite persistence.

UUID values are stored as canonical 36-character strings
(``xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx``). Domain code continues to use
``uuid.UUID``; conversion happens only in this adapter.

Timestamps are stored as ISO-8601 UTC strings with an explicit offset
(for example ``2026-09-22T08:00:00+00:00``). SQLite datetime affinity does
not preserve timezone, so naive stored values are treated as corruption and
rejected on load.
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

    impl = String(64)
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
                raise ValueError("persisted timestamp is missing timezone information")
            return value.astimezone(UTC)
        raw = str(value)
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("persisted timestamp is missing timezone information")
        return parsed.astimezone(UTC)
