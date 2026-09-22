"""AgentSession: AgentFlow's reference to an external coding-agent session."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from agentflow.core.domain.exceptions import DomainError
from agentflow.core.domain.mutation import GuardsStatusAssignment
from agentflow.core.domain.statuses import AgentSessionStatus
from agentflow.core.domain.time import (
    ensure_utc,
    require_not_before,
    require_updated_at_consistent,
    utc_now,
)
from agentflow.core.domain.transitions import AGENT_SESSION_TRANSITIONS, apply_transition
from agentflow.core.domain.validation import require_text


@dataclass
class AgentSession(GuardsStatusAssignment):
    """Generic handle for a session owned by some agent adapter.

    ``adapter_id`` selects the implementation. ``external_session_id`` is that
    adapter's own session key. Core does not interpret the key.
    """

    id: UUID
    adapter_id: str
    external_session_id: str
    created_at: datetime
    updated_at: datetime
    status: AgentSessionStatus = AgentSessionStatus.CREATED

    def __post_init__(self) -> None:
        require_text(self.adapter_id, "AgentSession adapter_id")
        require_text(self.external_session_id, "AgentSession external_session_id")
        if not isinstance(self.status, AgentSessionStatus):
            raise DomainError("AgentSession status must be an AgentSessionStatus")
        self.created_at = ensure_utc(self.created_at)
        self.updated_at = ensure_utc(self.updated_at)
        require_updated_at_consistent(self.created_at, self.updated_at)

    def transition_to(
        self,
        new_status: AgentSessionStatus,
        *,
        at: datetime | None = None,
    ) -> None:
        """Move the session to ``new_status`` when that edge is legal."""
        if not isinstance(new_status, AgentSessionStatus):
            raise DomainError("AgentSession status must be an AgentSessionStatus")
        moment = require_not_before(
            at if at is not None else utc_now(),
            self.updated_at,
            label="transition time",
            earliest_label="updated_at",
        )
        updated = apply_transition(
            entity="AgentSession",
            current=self.status,
            target=new_status,
            allowed=AGENT_SESSION_TRANSITIONS,
        )
        object.__setattr__(self, "status", updated)
        self.updated_at = moment


def create_agent_session(
    adapter_id: str,
    external_session_id: str,
    *,
    session_id: UUID | None = None,
    created_at: datetime | None = None,
) -> AgentSession:
    """Create a session reference in ``CREATED``."""
    created = ensure_utc(created_at) if created_at is not None else utc_now()
    return AgentSession(
        id=session_id or uuid4(),
        adapter_id=adapter_id,
        external_session_id=external_session_id,
        created_at=created,
        updated_at=created,
    )
