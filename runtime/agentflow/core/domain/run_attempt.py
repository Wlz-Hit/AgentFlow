"""RunAttempt: one try at executing a queue item."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from agentflow.core.domain.exceptions import DomainError
from agentflow.core.domain.mutation import GuardsStatusAssignment
from agentflow.core.domain.statuses import RunAttemptStatus, is_terminal_status
from agentflow.core.domain.time import ensure_utc, require_not_before, utc_now
from agentflow.core.domain.transitions import RUN_ATTEMPT_TRANSITIONS, apply_transition
from agentflow.core.domain.validation import require_positive_int, require_text

_STARTED_REQUIRED = frozenset(
    {
        RunAttemptStatus.RUNNING,
        RunAttemptStatus.WAITING_QUOTA,
        RunAttemptStatus.WAITING_USER,
        RunAttemptStatus.PAUSED,
        RunAttemptStatus.COMPLETED,
        RunAttemptStatus.FAILED,
    }
)


def _validate_run_attempt_fields(
    *,
    status: RunAttemptStatus,
    created_at: datetime,
    updated_at: datetime,
    started_at: datetime | None,
    finished_at: datetime | None,
    failure_reason: str | None,
) -> tuple[datetime, datetime, datetime | None, datetime | None]:
    """Enforce status/timing/failure_reason consistency for construction and reload."""
    created = ensure_utc(created_at)
    updated = ensure_utc(updated_at)
    started = ensure_utc(started_at) if started_at is not None else None
    finished = ensure_utc(finished_at) if finished_at is not None else None

    require_not_before(
        updated,
        created,
        label="updated_at",
        earliest_label="created_at",
    )

    if failure_reason is not None:
        if status is not RunAttemptStatus.FAILED:
            raise DomainError("failure_reason is only valid when status is FAILED")
        require_text(failure_reason, "RunAttempt failure_reason")

    if status is RunAttemptStatus.CREATED:
        if started is not None or finished is not None:
            raise DomainError("CREATED RunAttempt must not have started_at or finished_at")
        return created, updated, None, None

    if status in _STARTED_REQUIRED and started is None:
        raise DomainError(f"{status.value} RunAttempt requires started_at")

    if status is RunAttemptStatus.CANCELLED:
        if finished is None:
            raise DomainError("CANCELLED RunAttempt requires finished_at")
    elif is_terminal_status(status):
        if finished is None:
            raise DomainError(f"{status.value} RunAttempt requires finished_at")
    elif finished is not None:
        raise DomainError(f"{status.value} RunAttempt must not have finished_at")

    if started is not None:
        require_not_before(
            started,
            created,
            label="started_at",
            earliest_label="created_at",
        )
        require_not_before(
            updated,
            started,
            label="updated_at",
            earliest_label="started_at",
        )
    if finished is not None:
        require_not_before(
            finished,
            created,
            label="finished_at",
            earliest_label="created_at",
        )
        if started is not None:
            require_not_before(
                finished,
                started,
                label="finished_at",
                earliest_label="started_at",
            )
        require_not_before(
            updated,
            finished,
            label="updated_at",
            earliest_label="finished_at",
        )

    return created, updated, started, finished


@dataclass
class RunAttempt(GuardsStatusAssignment):
    """One execution attempt for a queue item.

    A queue item may own many attempts. Quota exhaustion, a user hold, or a
    pause leaves the attempt interrupted. ``FAILED`` is reserved for a
    terminal execution failure and carries an optional provider-neutral
    ``failure_reason``.

    ``CANCELLED`` may occur before the attempt starts (``started_at`` is then
    ``None``). ``COMPLETED`` and ``FAILED`` always originate from ``RUNNING``
    and therefore require ``started_at``.

    ``updated_at`` records the most recent successful lifecycle transition and
    is monotonic: later transitions may not use an earlier clock.
    """

    id: UUID
    queue_item_id: UUID
    agent_session_id: UUID
    attempt_number: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: str | None = None
    status: RunAttemptStatus = RunAttemptStatus.CREATED

    def __post_init__(self) -> None:
        require_positive_int(self.attempt_number, "RunAttempt attempt_number")
        if not isinstance(self.status, RunAttemptStatus):
            raise DomainError("RunAttempt status must be a RunAttemptStatus")
        created, updated, started, finished = _validate_run_attempt_fields(
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            failure_reason=self.failure_reason,
        )
        self.created_at = created
        self.updated_at = updated
        self.started_at = started
        self.finished_at = finished

    def transition_to(
        self,
        new_status: RunAttemptStatus,
        *,
        at: datetime | None = None,
        failure_reason: str | None = None,
    ) -> None:
        """Move the attempt to ``new_status`` when that edge is legal.

        ``failure_reason`` is accepted only on the transition into ``FAILED``.
        Entering ``RUNNING`` records ``started_at`` once. Entering a terminal
        status records ``finished_at``. Every success advances ``updated_at``.
        """
        if not isinstance(new_status, RunAttemptStatus):
            raise DomainError("RunAttempt status must be a RunAttemptStatus")
        if failure_reason is not None and new_status is not RunAttemptStatus.FAILED:
            raise DomainError("failure_reason is only valid when transitioning to FAILED")
        if failure_reason is not None:
            require_text(failure_reason, "RunAttempt failure_reason")

        moment = ensure_utc(at) if at is not None else utc_now()
        require_not_before(
            moment,
            self.updated_at,
            label="transition time",
            earliest_label="updated_at",
        )

        updated = apply_transition(
            entity="RunAttempt",
            current=self.status,
            target=new_status,
            allowed=RUN_ATTEMPT_TRANSITIONS,
        )
        object.__setattr__(self, "status", updated)
        if updated is RunAttemptStatus.RUNNING and self.started_at is None:
            self.started_at = moment
        if updated is RunAttemptStatus.FAILED and failure_reason is not None:
            self.failure_reason = failure_reason
        if is_terminal_status(updated):
            self.finished_at = moment
        self.updated_at = moment


def create_run_attempt(
    queue_item_id: UUID,
    agent_session_id: UUID,
    attempt_number: int,
    *,
    attempt_id: UUID | None = None,
    created_at: datetime | None = None,
) -> RunAttempt:
    """Create an attempt in ``CREATED`` with no start or finish time."""
    created = ensure_utc(created_at) if created_at is not None else utc_now()
    return RunAttempt(
        id=attempt_id or uuid4(),
        queue_item_id=queue_item_id,
        agent_session_id=agent_session_id,
        attempt_number=attempt_number,
        created_at=created,
        updated_at=created,
    )
