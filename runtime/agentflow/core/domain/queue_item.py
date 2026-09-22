"""QueueItem: a durable unit of work waiting to be dispatched."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from agentflow.core.domain.exceptions import DomainError
from agentflow.core.domain.mutation import GuardsStatusAssignment
from agentflow.core.domain.statuses import QueueItemStatus
from agentflow.core.domain.time import (
    ensure_utc,
    require_not_before,
    require_updated_at_consistent,
    utc_now,
)
from agentflow.core.domain.transitions import QUEUE_ITEM_TRANSITIONS, apply_transition
from agentflow.core.domain.validation import require_non_negative_int, require_text


@dataclass
class QueueItem(GuardsStatusAssignment):
    """Scheduled execution of work described by a workflow step.

    The step says what should happen. The queue item is the unit a future
    dispatcher will hand to an adapter. Optional scheduling fields can be
    added later without renaming the identity already stored here:
    ``depends_on``, ``condition``, ``retry_policy``, ``timeout``, and
    ``idempotency_key``.
    """

    id: UUID
    job_id: UUID
    workflow_step_id: UUID
    sequence: int
    prompt: str
    created_at: datetime
    available_at: datetime
    updated_at: datetime
    status: QueueItemStatus = QueueItemStatus.CREATED

    def __post_init__(self) -> None:
        require_non_negative_int(self.sequence, "QueueItem sequence")
        require_text(self.prompt, "QueueItem prompt")
        if not isinstance(self.status, QueueItemStatus):
            raise DomainError("QueueItem status must be a QueueItemStatus")
        self.created_at = ensure_utc(self.created_at)
        self.available_at = ensure_utc(self.available_at)
        self.updated_at = ensure_utc(self.updated_at)
        require_updated_at_consistent(self.created_at, self.updated_at)
        if self.available_at < self.created_at:
            raise DomainError("available_at must not be earlier than created_at")

    def transition_to(
        self,
        new_status: QueueItemStatus,
        *,
        at: datetime | None = None,
    ) -> None:
        """Move the queue item to ``new_status`` when that edge is legal."""
        if not isinstance(new_status, QueueItemStatus):
            raise DomainError("QueueItem status must be a QueueItemStatus")
        moment = require_not_before(
            at if at is not None else utc_now(),
            self.updated_at,
            label="transition time",
            earliest_label="updated_at",
        )
        updated = apply_transition(
            entity="QueueItem",
            current=self.status,
            target=new_status,
            allowed=QUEUE_ITEM_TRANSITIONS,
        )
        object.__setattr__(self, "status", updated)
        self.updated_at = moment


def create_queue_item(
    job_id: UUID,
    workflow_step_id: UUID,
    sequence: int,
    prompt: str,
    *,
    item_id: UUID | None = None,
    created_at: datetime | None = None,
    available_at: datetime | None = None,
) -> QueueItem:
    """Create a queue item in ``CREATED``.

    ``available_at`` defaults to the creation time, meaning the item is
    immediately eligible once a later scheduler moves it to ``READY``.
    """
    created = ensure_utc(created_at) if created_at is not None else utc_now()
    available = created if available_at is None else ensure_utc(available_at)
    return QueueItem(
        id=item_id or uuid4(),
        job_id=job_id,
        workflow_step_id=workflow_step_id,
        sequence=sequence,
        prompt=prompt,
        created_at=created,
        available_at=available,
        updated_at=created,
    )
