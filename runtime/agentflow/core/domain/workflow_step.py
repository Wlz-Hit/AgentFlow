"""WorkflowStep: one logical step inside a job."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from agentflow.core.domain.exceptions import DomainError
from agentflow.core.domain.mutation import GuardsStatusAssignment
from agentflow.core.domain.statuses import WorkflowStepStatus
from agentflow.core.domain.time import (
    ensure_utc,
    require_not_before,
    require_updated_at_consistent,
    utc_now,
)
from agentflow.core.domain.transitions import WORKFLOW_STEP_TRANSITIONS, apply_transition
from agentflow.core.domain.validation import require_non_negative_int, require_text


@dataclass
class WorkflowStep(GuardsStatusAssignment):
    """What should happen inside a job.

    Sequence orders steps. Dependency and DAG execution are intentionally
    absent; a later workflow engine can add them beside this type.
    """

    id: UUID
    job_id: UUID
    sequence: int
    title: str
    prompt: str
    created_at: datetime
    updated_at: datetime
    status: WorkflowStepStatus = WorkflowStepStatus.CREATED

    def __post_init__(self) -> None:
        require_non_negative_int(self.sequence, "WorkflowStep sequence")
        require_text(self.title, "WorkflowStep title")
        require_text(self.prompt, "WorkflowStep prompt")
        if not isinstance(self.status, WorkflowStepStatus):
            raise DomainError("WorkflowStep status must be a WorkflowStepStatus")
        self.created_at = ensure_utc(self.created_at)
        self.updated_at = ensure_utc(self.updated_at)
        require_updated_at_consistent(self.created_at, self.updated_at)

    def transition_to(
        self,
        new_status: WorkflowStepStatus,
        *,
        at: datetime | None = None,
    ) -> None:
        """Move the step to ``new_status`` when that edge is legal."""
        if not isinstance(new_status, WorkflowStepStatus):
            raise DomainError("WorkflowStep status must be a WorkflowStepStatus")
        moment = require_not_before(
            at if at is not None else utc_now(),
            self.updated_at,
            label="transition time",
            earliest_label="updated_at",
        )
        updated = apply_transition(
            entity="WorkflowStep",
            current=self.status,
            target=new_status,
            allowed=WORKFLOW_STEP_TRANSITIONS,
        )
        object.__setattr__(self, "status", updated)
        self.updated_at = moment


def create_workflow_step(
    job_id: UUID,
    sequence: int,
    title: str,
    prompt: str,
    *,
    step_id: UUID | None = None,
    created_at: datetime | None = None,
) -> WorkflowStep:
    """Create a workflow step in ``CREATED``."""
    created = ensure_utc(created_at) if created_at is not None else utc_now()
    return WorkflowStep(
        id=step_id or uuid4(),
        job_id=job_id,
        sequence=sequence,
        title=title,
        prompt=prompt,
        created_at=created,
        updated_at=created,
    )
