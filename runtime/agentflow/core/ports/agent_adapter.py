"""AgentAdapter port.

The Scheduler will call capabilities on this port, not provider names.

Intended operations (not implemented in TASK-001):

- start session
- resume session
- run input
- interrupt
- observe events
- query usage/quota
- health check
"""

from typing import Protocol


class AgentAdapter(Protocol):
    """Provider-agnostic coding-agent capabilities.

    Concrete adapters (Codex, Claude Code, Gemini CLI, …) live under
    ``agentflow.adapters`` and must not be imported from core.
    """

    def adapter_id(self) -> str:
        """Stable identifier for the adapter implementation."""
        ...
