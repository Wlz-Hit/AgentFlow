"""SQLAlchemy unit of work: one session, one atomic commit boundary."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from agentflow.persistence.repositories import (
    SqlAlchemyAgentSessionRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyQueueItemRepository,
    SqlAlchemyRunAttemptRepository,
    SqlAlchemyWorkflowStepRepository,
)


class SqlAlchemyUnitOfWork:
    """Binds all repositories to one SQLAlchemy session.

    Use as a context manager. Call ``commit()`` explicitly to persist. Leaving
    the context without commit rolls back. Exceptions also roll back.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None
        self.jobs: SqlAlchemyJobRepository
        self.workflow_steps: SqlAlchemyWorkflowStepRepository
        self.queue_items: SqlAlchemyQueueItemRepository
        self.agent_sessions: SqlAlchemyAgentSessionRepository
        self.run_attempts: SqlAlchemyRunAttemptRepository

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self.session = self._session_factory()
        self.jobs = SqlAlchemyJobRepository(self.session)
        self.workflow_steps = SqlAlchemyWorkflowStepRepository(self.session)
        self.queue_items = SqlAlchemyQueueItemRepository(self.session)
        self.agent_sessions = SqlAlchemyAgentSessionRepository(self.session)
        self.run_attempts = SqlAlchemyRunAttemptRepository(self.session)
        return self

    def __exit__(self, exc_type: type[BaseException] | None, *_: object) -> None:
        assert self.session is not None
        try:
            if exc_type is not None:
                self.session.rollback()
            elif self.session.in_transaction():
                # Uncommitted work must not leak across process-style restarts.
                self.session.rollback()
        finally:
            self.session.close()
            self.session = None

    def commit(self) -> None:
        assert self.session is not None
        self.session.commit()

    def rollback(self) -> None:
        assert self.session is not None
        self.session.rollback()


@contextmanager
def unit_of_work(session_factory: sessionmaker[Session]) -> Iterator[SqlAlchemyUnitOfWork]:
    with SqlAlchemyUnitOfWork(session_factory) as uow:
        yield uow
