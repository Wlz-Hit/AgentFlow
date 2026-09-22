"""Provider-independent domain model.

These types are plain Python. Persistence mapping and provider adapters live
outside this package.
"""

from agentflow.core.domain.agent_session import AgentSession, create_agent_session
from agentflow.core.domain.exceptions import DomainError, InvalidStateTransition
from agentflow.core.domain.job import Job, create_job
from agentflow.core.domain.queue_item import QueueItem, create_queue_item
from agentflow.core.domain.run_attempt import RunAttempt, create_run_attempt
from agentflow.core.domain.statuses import (
    AgentSessionStatus,
    JobStatus,
    QueueItemStatus,
    RunAttemptStatus,
    WorkflowStepStatus,
    is_recoverable_status,
    is_terminal_status,
)
from agentflow.core.domain.workflow_step import WorkflowStep, create_workflow_step

__all__ = [
    "AgentSession",
    "AgentSessionStatus",
    "DomainError",
    "InvalidStateTransition",
    "Job",
    "JobStatus",
    "QueueItem",
    "QueueItemStatus",
    "RunAttempt",
    "RunAttemptStatus",
    "WorkflowStep",
    "WorkflowStepStatus",
    "create_agent_session",
    "create_job",
    "create_queue_item",
    "create_run_attempt",
    "create_workflow_step",
    "is_recoverable_status",
    "is_terminal_status",
]
