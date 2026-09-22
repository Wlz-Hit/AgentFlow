"""SQLAlchemy repository adapters. Return domain entities only."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentflow.core.domain.agent_session import AgentSession
from agentflow.core.domain.exceptions import DomainError
from agentflow.core.domain.job import Job
from agentflow.core.domain.queue_item import QueueItem
from agentflow.core.domain.run_attempt import RunAttempt
from agentflow.core.domain.statuses import is_active_run_attempt_status
from agentflow.core.domain.workflow_step import WorkflowStep
from agentflow.persistence import mappers
from agentflow.persistence.models import (
    AgentSessionRow,
    JobRow,
    QueueItemRow,
    RunAttemptRow,
    WorkflowStepRow,
)

_ACTIVE_STATUSES = (
    "created",
    "running",
    "waiting_quota",
    "waiting_user",
    "paused",
)


class SqlAlchemyJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, job: Job) -> None:
        row = self._session.get(JobRow, job.id)
        self._session.add(mappers.job_to_row(job, row))
        self._session.flush()

    def get(self, job_id: UUID) -> Job | None:
        row = self._session.get(JobRow, job_id)
        return mappers.job_from_row(row) if row is not None else None


class SqlAlchemyWorkflowStepRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, step: WorkflowStep) -> None:
        row = self._session.get(WorkflowStepRow, step.id)
        self._session.add(mappers.workflow_step_to_row(step, row))
        self._session.flush()

    def get(self, step_id: UUID) -> WorkflowStep | None:
        row = self._session.get(WorkflowStepRow, step_id)
        return mappers.workflow_step_from_row(row) if row is not None else None

    def list_for_job(self, job_id: UUID) -> list[WorkflowStep]:
        rows = self._session.scalars(
            select(WorkflowStepRow)
            .where(WorkflowStepRow.job_id == job_id)
            .order_by(WorkflowStepRow.sequence, WorkflowStepRow.created_at)
        ).all()
        return [mappers.workflow_step_from_row(row) for row in rows]


class SqlAlchemyQueueItemRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, item: QueueItem) -> None:
        row = self._session.get(QueueItemRow, item.id)
        self._session.add(mappers.queue_item_to_row(item, row))
        self._session.flush()

    def get(self, item_id: UUID) -> QueueItem | None:
        row = self._session.get(QueueItemRow, item_id)
        return mappers.queue_item_from_row(row) if row is not None else None

    def list_for_job(self, job_id: UUID) -> list[QueueItem]:
        rows = self._session.scalars(
            select(QueueItemRow)
            .where(QueueItemRow.job_id == job_id)
            .order_by(QueueItemRow.sequence, QueueItemRow.created_at)
        ).all()
        return [mappers.queue_item_from_row(row) for row in rows]

    def list_for_workflow_step(self, step_id: UUID) -> list[QueueItem]:
        rows = self._session.scalars(
            select(QueueItemRow)
            .where(QueueItemRow.workflow_step_id == step_id)
            .order_by(QueueItemRow.sequence, QueueItemRow.created_at)
        ).all()
        return [mappers.queue_item_from_row(row) for row in rows]


class SqlAlchemyAgentSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, session: AgentSession) -> None:
        row = self._session.get(AgentSessionRow, session.id)
        self._session.add(mappers.agent_session_to_row(session, row))
        self._session.flush()

    def get(self, session_id: UUID) -> AgentSession | None:
        row = self._session.get(AgentSessionRow, session_id)
        return mappers.agent_session_from_row(row) if row is not None else None

    def get_by_external(
        self,
        adapter_id: str,
        external_session_id: str,
    ) -> AgentSession | None:
        row = self._session.scalar(
            select(AgentSessionRow).where(
                AgentSessionRow.adapter_id == adapter_id,
                AgentSessionRow.external_session_id == external_session_id,
            )
        )
        return mappers.agent_session_from_row(row) if row is not None else None


class SqlAlchemyRunAttemptRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, attempt: RunAttempt) -> None:
        if is_active_run_attempt_status(attempt.status):
            existing = self.get_active_for_queue_item(attempt.queue_item_id)
            if existing is not None and existing.id != attempt.id:
                raise DomainError(
                    "QueueItem may have at most one non-terminal RunAttempt at a time"
                )
        row = self._session.get(RunAttemptRow, attempt.id)
        self._session.add(mappers.run_attempt_to_row(attempt, row))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            message = str(exc.orig) if getattr(exc, "orig", None) is not None else str(exc)
            lowered = message.lower()
            if (
                "uq_run_attempts_one_active_per_queue_item" in lowered
                or "one_active" in lowered
            ):
                raise DomainError(
                    "QueueItem may have at most one non-terminal RunAttempt at a time"
                ) from exc
            if (
                "uq_run_attempts_queue_item_attempt_number" in lowered
                or "attempt_number" in lowered
            ):
                raise DomainError(
                    "RunAttempt attempt_number must be unique per QueueItem"
                ) from exc
            raise

    def get(self, attempt_id: UUID) -> RunAttempt | None:
        row = self._session.get(RunAttemptRow, attempt_id)
        return mappers.run_attempt_from_row(row) if row is not None else None

    def list_for_queue_item(self, queue_item_id: UUID) -> list[RunAttempt]:
        rows = self._session.scalars(
            select(RunAttemptRow)
            .where(RunAttemptRow.queue_item_id == queue_item_id)
            .order_by(RunAttemptRow.attempt_number)
        ).all()
        return [mappers.run_attempt_from_row(row) for row in rows]

    def get_active_for_queue_item(self, queue_item_id: UUID) -> RunAttempt | None:
        row = self._session.scalar(
            select(RunAttemptRow).where(
                RunAttemptRow.queue_item_id == queue_item_id,
                RunAttemptRow.status.in_(_ACTIVE_STATUSES),
            )
        )
        return mappers.run_attempt_from_row(row) if row is not None else None
