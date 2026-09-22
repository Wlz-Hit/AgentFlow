"""Provider-independent durable runtime event model.

This is control-plane history for Scheduler, Recovery, Prompt Queue visibility,
debugging, desktop Timeline, and future WebSocket replay. It is not a full
Event Sourcing store: current-state tables remain authoritative.

High-frequency provider telemetry (token deltas, stdout chunks) does not belong
here and will use a different mechanism later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from agentflow.core.domain.exceptions import DomainError
from agentflow.core.domain.time import ensure_utc, utc_now

# Stable dotted lowercase names. Adapters normalize provider events onto these.
JOB_CREATED = "job.created"
JOB_STATUS_CHANGED = "job.status_changed"
WORKFLOW_STEP_CREATED = "workflow_step.created"
WORKFLOW_STEP_STATUS_CHANGED = "workflow_step.status_changed"
QUEUE_ITEM_ENQUEUED = "queue_item.enqueued"
QUEUE_ITEM_STATUS_CHANGED = "queue_item.status_changed"
AGENT_SESSION_CREATED = "agent_session.created"
AGENT_SESSION_STATUS_CHANGED = "agent_session.status_changed"
RUN_ATTEMPT_CREATED = "run_attempt.created"
RUN_ATTEMPT_STATUS_CHANGED = "run_attempt.status_changed"
QUOTA_EXHAUSTED = "quota.exhausted"
QUOTA_RESTORED = "quota.restored"
RECOVERY_SCHEDULED = "recovery.scheduled"
RUN_RESUMED = "run.resumed"
RUN_COMPLETED = "run.completed"


def ensure_json_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Reject non-JSON-serializable payload values at the domain boundary."""
    if not isinstance(payload, dict):
        raise DomainError("event payload must be a dict")
    try:
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise DomainError("event payload must be JSON-serializable") from exc
    if not isinstance(decoded, dict):
        raise DomainError("event payload must decode to a JSON object")
    return decoded


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """Immutable control-plane lifecycle event."""

    id: UUID
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    aggregate_type: str | None = None
    aggregate_id: UUID | None = None
    job_id: UUID | None = None
    correlation_id: UUID | None = None
    causation_id: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise DomainError("event_type must not be blank")
        object.__setattr__(self, "occurred_at", ensure_utc(self.occurred_at))
        object.__setattr__(self, "payload", ensure_json_payload(dict(self.payload)))


@dataclass(frozen=True, slots=True)
class StoredEvent:
    """Event plus local persistence ordering position for replay."""

    position: int
    event: RuntimeEvent

    def __post_init__(self) -> None:
        if not isinstance(self.position, int) or self.position < 1:
            raise DomainError("event position must be a positive integer")


def create_runtime_event(
    event_type: str,
    *,
    payload: dict[str, Any] | None = None,
    aggregate_type: str | None = None,
    aggregate_id: UUID | None = None,
    job_id: UUID | None = None,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
    event_id: UUID | None = None,
    occurred_at: datetime | None = None,
) -> RuntimeEvent:
    """Factory for a new immutable runtime event."""
    return RuntimeEvent(
        id=event_id or uuid4(),
        event_type=event_type,
        occurred_at=ensure_utc(occurred_at) if occurred_at is not None else utc_now(),
        payload=payload or {},
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        job_id=job_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )
