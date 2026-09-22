"""Explicit domain ↔ ORM mapping. ORM rows never leave the persistence package."""

from agentflow.core.domain.agent_session import AgentSession
from agentflow.core.domain.job import Job
from agentflow.core.domain.queue_item import QueueItem
from agentflow.core.domain.run_attempt import RunAttempt
from agentflow.core.domain.statuses import (
    AgentSessionStatus,
    JobStatus,
    QueueItemStatus,
    RunAttemptStatus,
    WorkflowStepStatus,
)
from agentflow.core.domain.workflow_step import WorkflowStep
from agentflow.persistence.models import (
    AgentSessionRow,
    JobRow,
    QueueItemRow,
    RunAttemptRow,
    WorkflowStepRow,
)


def job_to_row(job: Job, row: JobRow | None = None) -> JobRow:
    target = row or JobRow(id=job.id)
    target.id = job.id
    target.title = job.title
    target.description = job.description
    target.status = job.status.value
    target.created_at = job.created_at
    target.updated_at = job.updated_at
    return target


def job_from_row(row: JobRow) -> Job:
    return Job(
        id=row.id,
        title=row.title,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
        status=JobStatus(row.status),
    )


def workflow_step_to_row(step: WorkflowStep, row: WorkflowStepRow | None = None) -> WorkflowStepRow:
    target = row or WorkflowStepRow(id=step.id)
    target.id = step.id
    target.job_id = step.job_id
    target.sequence = step.sequence
    target.title = step.title
    target.prompt = step.prompt
    target.status = step.status.value
    target.created_at = step.created_at
    target.updated_at = step.updated_at
    return target


def workflow_step_from_row(row: WorkflowStepRow) -> WorkflowStep:
    return WorkflowStep(
        id=row.id,
        job_id=row.job_id,
        sequence=row.sequence,
        title=row.title,
        prompt=row.prompt,
        created_at=row.created_at,
        updated_at=row.updated_at,
        status=WorkflowStepStatus(row.status),
    )


def queue_item_to_row(item: QueueItem, row: QueueItemRow | None = None) -> QueueItemRow:
    target = row or QueueItemRow(id=item.id)
    target.id = item.id
    target.job_id = item.job_id
    target.workflow_step_id = item.workflow_step_id
    target.sequence = item.sequence
    target.prompt = item.prompt
    target.status = item.status.value
    target.created_at = item.created_at
    target.available_at = item.available_at
    target.updated_at = item.updated_at
    return target


def queue_item_from_row(row: QueueItemRow) -> QueueItem:
    return QueueItem(
        id=row.id,
        job_id=row.job_id,
        workflow_step_id=row.workflow_step_id,
        sequence=row.sequence,
        prompt=row.prompt,
        created_at=row.created_at,
        available_at=row.available_at,
        updated_at=row.updated_at,
        status=QueueItemStatus(row.status),
    )


def agent_session_to_row(
    session: AgentSession,
    row: AgentSessionRow | None = None,
) -> AgentSessionRow:
    target = row or AgentSessionRow(id=session.id)
    target.id = session.id
    target.adapter_id = session.adapter_id
    target.external_session_id = session.external_session_id
    target.status = session.status.value
    target.created_at = session.created_at
    target.updated_at = session.updated_at
    return target


def agent_session_from_row(row: AgentSessionRow) -> AgentSession:
    return AgentSession(
        id=row.id,
        adapter_id=row.adapter_id,
        external_session_id=row.external_session_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        status=AgentSessionStatus(row.status),
    )


def run_attempt_to_row(attempt: RunAttempt, row: RunAttemptRow | None = None) -> RunAttemptRow:
    target = row or RunAttemptRow(id=attempt.id)
    target.id = attempt.id
    target.queue_item_id = attempt.queue_item_id
    target.agent_session_id = attempt.agent_session_id
    target.attempt_number = attempt.attempt_number
    target.status = attempt.status.value
    target.created_at = attempt.created_at
    target.updated_at = attempt.updated_at
    target.started_at = attempt.started_at
    target.finished_at = attempt.finished_at
    target.failure_reason = attempt.failure_reason
    return target


def run_attempt_from_row(row: RunAttemptRow) -> RunAttempt:
    return RunAttempt(
        id=row.id,
        queue_item_id=row.queue_item_id,
        agent_session_id=row.agent_session_id,
        attempt_number=row.attempt_number,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        failure_reason=row.failure_reason,
        status=RunAttemptStatus(row.status),
    )
