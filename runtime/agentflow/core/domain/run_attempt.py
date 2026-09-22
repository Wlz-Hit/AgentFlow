"""RunAttempt: one try at executing a queue item."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from agentflow.core.domain.exceptions import DomainError
from agentflow.core.domain.mutation import GuardsStatusAssignment
from agentflow.core.domain.statuses import RunAttemptStatus, is_terminal_status
from agentflow.core.domain.time import ensure_utc, utc_now
from agentflow.core.domain.transitions import RUN_ATTEMPT_TRANSITIONS, apply_transition
from agentflow.core.domain.validation import require_positive_int, require_text


@dataclass
class RunAttempt(GuardsStatusAssignment):
    """One execution attempt for a queue item.

    A queue item may own many attempts. Quota exhaustion, a user hold, or a
    pause leaves the attempt interrupted. ``FAILED`` is reserved for a
    terminal execution failure and carries an optional provider-neutral
    ``failure_reason``.
    """

    id: UUID
    queue_item_id: UUID
    agent_session_id: UUID
    attempt_number: int
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: str | None = None
    status: RunAttemptStatus = RunAttemptStatus.CREATED

    def __post_init__(self) -> None:
        require_positive_int(self.attempt_number, "RunAttempt attempt_number")
        if not isinstance(self.status, RunAttemptStatus):
            raise DomainError("RunAttempt status must be a RunAttemptStatus")
        if self.failure_reason is not None:
            require_text(self.failure_reason, "RunAttempt failure_reason")
        self.created_at = ensure_utc(self.created_at)
        if self.started_at is not None:
            self.started_at = ensure_utc(self.started_at)
        if self.finished_at is not None:
            self.finished_at = ensure_utc(self.finished_at)

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
        status records ``finished_at``.
        """
        if not isinstance(new_status, RunAttemptStatus):
            raise DomainError("RunAttempt status must be a RunAttemptStatus")
        if failure_reason is not None and new_status is not RunAttemptStatus.FAILED:
            raise DomainError("failure_reason is only valid when transitioning to FAILED")
        if failure_reason is not None:
            require_text(failure_reason, "RunAttempt failure_reason")
        moment = ensure_utc(at) if at is not None else utc_now()
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
    )
