"""Provider-independent domain exceptions."""


class DomainError(Exception):
    """Base error for illegal or inconsistent domain operations."""


class InvalidStateTransition(DomainError):
    """Raised when an entity moves to a status its lifecycle does not allow."""

    def __init__(self, entity: str, current: str, target: str) -> None:
        self.entity = entity
        self.current = current
        self.target = target
        super().__init__(
            f"Illegal {entity} state transition from {current} to {target}"
        )
