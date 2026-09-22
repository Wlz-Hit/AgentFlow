"""Explicit legal state transitions for domain entities.

Status changes go through :func:`apply_transition`. Callers do not assign a new
status string and hope it is valid.
"""

from collections.abc import Mapping
from enum import StrEnum

from agentflow.core.domain.exceptions import InvalidStateTransition
from agentflow.core.domain.statuses import (
    AgentSessionStatus,
    JobStatus,
    QueueItemStatus,
    RunAttemptStatus,
    WorkflowStepStatus,
)

# Job, workflow step, and queue item share this graph today. The enums stay
# separate so one entity can gain states later without rewriting the others.
_WORK_LIFECYCLE: dict[str, frozenset[str]] = {
    "created": frozenset({"ready", "cancelled"}),
    "ready": frozenset({"running", "paused", "cancelled"}),
    "running": frozenset(
        {
            "completed",
            "failed",
            "paused",
            "waiting_user",
            "waiting_quota",
            "cancelled",
        }
    ),
    "paused": frozenset({"ready", "running", "cancelled"}),
    "waiting_user": frozenset({"ready", "running", "cancelled"}),
    "waiting_quota": frozenset({"ready", "running", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


def _table[S: StrEnum](
    enum_type: type[S],
    graph: Mapping[str, frozenset[str]],
) -> dict[S, frozenset[S]]:
    return {
        enum_type(source): frozenset(enum_type(target) for target in targets)
        for source, targets in graph.items()
    }


JOB_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = _table(JobStatus, _WORK_LIFECYCLE)
WORKFLOW_STEP_TRANSITIONS: dict[WorkflowStepStatus, frozenset[WorkflowStepStatus]] = _table(
    WorkflowStepStatus, _WORK_LIFECYCLE
)
QUEUE_ITEM_TRANSITIONS: dict[QueueItemStatus, frozenset[QueueItemStatus]] = _table(
    QueueItemStatus, _WORK_LIFECYCLE
)

AGENT_SESSION_TRANSITIONS: dict[AgentSessionStatus, frozenset[AgentSessionStatus]] = {
    AgentSessionStatus.CREATED: frozenset(
        {AgentSessionStatus.ACTIVE, AgentSessionStatus.CANCELLED}
    ),
    AgentSessionStatus.ACTIVE: frozenset(
        {
            AgentSessionStatus.PAUSED,
            AgentSessionStatus.WAITING_USER,
            AgentSessionStatus.WAITING_QUOTA,
            AgentSessionStatus.CLOSED,
            AgentSessionStatus.FAILED,
            AgentSessionStatus.CANCELLED,
        }
    ),
    AgentSessionStatus.PAUSED: frozenset(
        {AgentSessionStatus.ACTIVE, AgentSessionStatus.CANCELLED}
    ),
    AgentSessionStatus.WAITING_USER: frozenset(
        {AgentSessionStatus.ACTIVE, AgentSessionStatus.CANCELLED}
    ),
    AgentSessionStatus.WAITING_QUOTA: frozenset(
        {AgentSessionStatus.ACTIVE, AgentSessionStatus.CANCELLED}
    ),
    AgentSessionStatus.CLOSED: frozenset(),
    AgentSessionStatus.FAILED: frozenset(),
    AgentSessionStatus.CANCELLED: frozenset(),
}

RUN_ATTEMPT_TRANSITIONS: dict[RunAttemptStatus, frozenset[RunAttemptStatus]] = {
    RunAttemptStatus.CREATED: frozenset(
        {RunAttemptStatus.RUNNING, RunAttemptStatus.CANCELLED}
    ),
    RunAttemptStatus.RUNNING: frozenset(
        {
            RunAttemptStatus.WAITING_QUOTA,
            RunAttemptStatus.WAITING_USER,
            RunAttemptStatus.PAUSED,
            RunAttemptStatus.COMPLETED,
            RunAttemptStatus.FAILED,
            RunAttemptStatus.CANCELLED,
        }
    ),
    RunAttemptStatus.WAITING_QUOTA: frozenset(
        {RunAttemptStatus.RUNNING, RunAttemptStatus.CANCELLED}
    ),
    RunAttemptStatus.WAITING_USER: frozenset(
        {RunAttemptStatus.RUNNING, RunAttemptStatus.CANCELLED}
    ),
    RunAttemptStatus.PAUSED: frozenset(
        {RunAttemptStatus.RUNNING, RunAttemptStatus.CANCELLED}
    ),
    RunAttemptStatus.COMPLETED: frozenset(),
    RunAttemptStatus.FAILED: frozenset(),
    RunAttemptStatus.CANCELLED: frozenset(),
}


def apply_transition[S: StrEnum](
    *,
    entity: str,
    current: S,
    target: S,
    allowed: Mapping[S, frozenset[S]],
) -> S:
    """Return ``target`` when the move is legal; otherwise raise."""
    legal = allowed.get(current, frozenset())
    if target not in legal:
        raise InvalidStateTransition(entity, current.value, target.value)
    return target
