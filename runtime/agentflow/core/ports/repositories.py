"""Repository ports for durable domain persistence.

Application and core services depend on these protocols. SQLAlchemy adapters
live under ``agentflow.persistence`` and must not be imported from core.
"""

from typing import Protocol
from uuid import UUID

from agentflow.core.domain.agent_session import AgentSession
from agentflow.core.domain.job import Job
from agentflow.core.domain.queue_item import QueueItem
from agentflow.core.domain.run_attempt import RunAttempt
from agentflow.core.domain.workflow_step import WorkflowStep
from agentflow.core.events import RuntimeEvent, StoredEvent


class JobRepository(Protocol):
    def save(self, job: Job) -> None: ...

    def get(self, job_id: UUID) -> Job | None: ...


class WorkflowStepRepository(Protocol):
    def save(self, step: WorkflowStep) -> None: ...

    def get(self, step_id: UUID) -> WorkflowStep | None: ...

    def list_for_job(self, job_id: UUID) -> list[WorkflowStep]: ...


class QueueItemRepository(Protocol):
    def save(self, item: QueueItem) -> None: ...

    def get(self, item_id: UUID) -> QueueItem | None: ...

    def list_for_job(self, job_id: UUID) -> list[QueueItem]: ...

    def list_for_workflow_step(self, step_id: UUID) -> list[QueueItem]: ...


class AgentSessionRepository(Protocol):
    def save(self, session: AgentSession) -> None: ...

    def get(self, session_id: UUID) -> AgentSession | None: ...

    def get_by_external(
        self,
        adapter_id: str,
        external_session_id: str,
    ) -> AgentSession | None: ...


class RunAttemptRepository(Protocol):
    def save(self, attempt: RunAttempt) -> None: ...

    def get(self, attempt_id: UUID) -> RunAttempt | None: ...

    def list_for_queue_item(self, queue_item_id: UUID) -> list[RunAttempt]: ...

    def get_active_for_queue_item(self, queue_item_id: UUID) -> RunAttempt | None: ...


class EventRepository(Protocol):
    """Append-only durable control-plane event store."""

    def append(self, event: RuntimeEvent) -> StoredEvent: ...

    def get(self, event_id: UUID) -> StoredEvent | None: ...

    def list_after(self, position: int) -> list[StoredEvent]: ...

    def list_for_job(self, job_id: UUID) -> list[StoredEvent]: ...


class UnitOfWork(Protocol):
    """Atomic boundary for one application operation.

    Repositories share one underlying transaction. ``commit`` persists every
    change made through the repositories; ``rollback`` discards them.
    Constraint translation inside a repository must not roll back unrelated
    work already pending in the same UnitOfWork; use savepoints instead.
    """

    jobs: JobRepository
    workflow_steps: WorkflowStepRepository
    queue_items: QueueItemRepository
    agent_sessions: AgentSessionRepository
    run_attempts: RunAttemptRepository
    events: EventRepository

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
