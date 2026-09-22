"""Job: a user-level unit of work."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from agentflow.core.domain.exceptions import DomainError
from agentflow.core.domain.mutation import GuardsStatusAssignment
from agentflow.core.domain.statuses import JobStatus
from agentflow.core.domain.time import (
    ensure_utc,
    require_not_before,
    require_updated_at_consistent,
    utc_now,
)
from agentflow.core.domain.transitions import JOB_TRANSITIONS, apply_transition
from agentflow.core.domain.validation import require_text


@dataclass
class Job(GuardsStatusAssignment):
    """User-level unit of work composed of workflow steps.

    Provider identity stays on agent sessions and adapters. A job records
    title, description, and lifecycle only.
    """

    id: UUID
    title: str
    description: str
    created_at: datetime
    updated_at: datetime
    status: JobStatus = JobStatus.CREATED

    def __post_init__(self) -> None:
        require_text(self.title, "Job title")
        if not isinstance(self.description, str):
            raise DomainError("Job description must be a string")
        if not isinstance(self.status, JobStatus):
            raise DomainError("Job status must be a JobStatus")
        self.created_at = ensure_utc(self.created_at)
        self.updated_at = ensure_utc(self.updated_at)
        require_updated_at_consistent(self.created_at, self.updated_at)

    def transition_to(self, new_status: JobStatus, *, at: datetime | None = None) -> None:
        """Move the job to ``new_status`` when that edge is legal."""
        if not isinstance(new_status, JobStatus):
            raise DomainError("Job status must be a JobStatus")
        moment = require_not_before(
            at if at is not None else utc_now(),
            self.updated_at,
            label="transition time",
            earliest_label="updated_at",
        )
        updated = apply_transition(
            entity="Job",
            current=self.status,
            target=new_status,
            allowed=JOB_TRANSITIONS,
        )
        object.__setattr__(self, "status", updated)
        self.updated_at = moment


def create_job(
    title: str,
    description: str = "",
    *,
    job_id: UUID | None = None,
    created_at: datetime | None = None,
) -> Job:
    """Create a job in ``CREATED``."""
    created = ensure_utc(created_at) if created_at is not None else utc_now()
    return Job(
        id=job_id or uuid4(),
        title=title,
        description=description,
        created_at=created,
        updated_at=created,
    )
