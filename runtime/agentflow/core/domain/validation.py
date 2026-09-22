"""Shared construction checks for domain values."""

from agentflow.core.domain.exceptions import DomainError


def require_text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DomainError(f"{label} must not be blank")


def require_non_negative_int(value: object, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DomainError(f"{label} must be a non-negative integer")


def require_positive_int(value: object, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DomainError(f"{label} must be a positive integer")
