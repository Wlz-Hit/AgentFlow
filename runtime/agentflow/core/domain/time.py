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


def require_not_before(
    value: datetime,
    earliest: datetime,
    *,
    label: str,
    earliest_label: str = "the previous timestamp",
) -> datetime:
    """Return ``value`` in UTC when it is not earlier than ``earliest``."""
    moment = ensure_utc(value)
    floor = ensure_utc(earliest)
    if moment < floor:
        raise DomainError(f"{label} must not be earlier than {earliest_label}")
    return moment


def require_updated_at_consistent(created_at: datetime, updated_at: datetime) -> None:
    """Reject ``updated_at`` that precedes ``created_at``."""
    require_not_before(
        updated_at,
        created_at,
        label="updated_at",
        earliest_label="created_at",
    )
