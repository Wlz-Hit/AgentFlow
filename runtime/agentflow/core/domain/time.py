"""Small timestamp helpers for domain entities."""

from datetime import UTC, datetime

from agentflow.core.domain.exceptions import DomainError


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC.

    Naive values are rejected so persistence and recovery never guess a zone.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainError("timestamps must be timezone-aware")
    return value.astimezone(UTC)
