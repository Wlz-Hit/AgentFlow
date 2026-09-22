"""Lifecycle statuses for core domain entities.

Each entity has its own enum. Shared words such as ``running`` do not mean the
entities share one state machine.
"""

from enum import StrEnum

_TERMINAL_VALUES = frozenset({"completed", "failed", "cancelled", "closed"})
_RECOVERABLE_VALUES = frozenset({"paused", "waiting_user", "waiting_quota"})


class JobStatus(StrEnum):
    """Lifecycle of a user-level unit of work."""

    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_USER = "waiting_user"
    WAITING_QUOTA = "waiting_quota"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStepStatus(StrEnum):
    """Lifecycle of one logical step inside a job.

    A step describes the work. It is not a dispatched execution unit.
    """

    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_USER = "waiting_user"
    WAITING_QUOTA = "waiting_quota"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueueItemStatus(StrEnum):
    """Lifecycle of a durable unit waiting to be dispatched."""

    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_USER = "waiting_user"
    WAITING_QUOTA = "waiting_quota"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentSessionStatus(StrEnum):
    """Lifecycle of a generic reference to an external coding-agent session.

    ``ACTIVE`` means the external session is open. ``CLOSED`` is a clean end.
    Neither is the success or failure of a particular run attempt.
    """

    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    WAITING_USER = "waiting_user"
    WAITING_QUOTA = "waiting_quota"
    CLOSED = "closed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunAttemptStatus(StrEnum):
    """Lifecycle of one execution attempt for a queue item.

    ``WAITING_QUOTA`` is an interruption. It is not a terminal failure.
    Attempts have no ``READY`` state: a fresh attempt is ``CREATED`` until it
    starts, and a quota-interrupted attempt resumes to ``RUNNING``.
    """

    CREATED = "created"
    RUNNING = "running"
    WAITING_QUOTA = "waiting_quota"
    WAITING_USER = "waiting_user"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def is_terminal_status(status: StrEnum) -> bool:
    """Return whether the status ends the entity's lifecycle."""
    return status.value in _TERMINAL_VALUES


def is_recoverable_status(status: StrEnum) -> bool:
    """Return whether the status is an interruption that can resume later."""
    return status.value in _RECOVERABLE_VALUES


def is_active_run_attempt_status(status: RunAttemptStatus) -> bool:
    """Return whether the attempt still occupies the queue item's active slot."""
    return not is_terminal_status(status)
