"""Status changes are allowed only through transition methods."""

from agentflow.core.domain.exceptions import DomainError


class GuardsStatusAssignment:
    """Reject ``entity.status = ...`` after construction.

    Initial construction may set ``status`` (including when a future
    persistence adapter reloads a stored entity). Later changes must call
    ``transition_to`` so the lifecycle table is enforced.
    """

    def __setattr__(self, name: str, value: object) -> None:
        if name == "status" and "status" in self.__dict__:
            raise DomainError(
                f"{type(self).__name__} status must change through transition_to()"
            )
        super().__setattr__(name, value)
