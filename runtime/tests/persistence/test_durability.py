"""Restart-durable SQLite persistence integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from agentflow.core.domain.agent_session import create_agent_session
from agentflow.core.domain.exceptions import DomainError
from agentflow.core.domain.job import create_job
from agentflow.core.domain.queue_item import create_queue_item
from agentflow.core.domain.run_attempt import create_run_attempt
from agentflow.core.domain.statuses import (
    AgentSessionStatus,
    JobStatus,
    QueueItemStatus,
    RunAttemptStatus,
    WorkflowStepStatus,
)
from agentflow.core.domain.workflow_step import create_workflow_step
from agentflow.persistence.database import create_sqlite_engine, session_factory
from agentflow.persistence.unit_of_work import SqlAlchemyUnitOfWork
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

T0 = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
T1 = datetime(2026, 9, 22, 8, 5, tzinfo=UTC)
T2 = datetime(2026, 9, 22, 8, 10, tzinfo=UTC)
RUNTIME_ROOT = Path(__file__).resolve().parents[2]


def _migrate(db_path: Path) -> None:
    cfg = Config(str(RUNTIME_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(RUNTIME_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(cfg, "head")


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    path = tmp_path / "agentflow.db"
    _migrate(path)
    return f"sqlite:///{path.as_posix()}"


def _reopen(db_url: str) -> SqlAlchemyUnitOfWork:
    engine = create_sqlite_engine(db_url)
    return SqlAlchemyUnitOfWork(session_factory(engine))


def test_alembic_migration_creates_domain_tables(tmp_path: Path) -> None:
    path = tmp_path / "migrated.db"
    _migrate(path)
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
    assert {
        "jobs",
        "workflow_steps",
        "queue_items",
        "agent_sessions",
        "run_attempts",
        "alembic_version",
    } <= tables


def test_job_round_trip_survives_close_reopen(db_url: str) -> None:
    job = create_job("Persist me", "body", created_at=T0)
    job.transition_to(JobStatus.READY, at=T1)
    job_id = job.id

    with _reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.commit()

    with _reopen(db_url) as uow:
        loaded = uow.jobs.get(job_id)

    assert loaded is not None
    assert loaded.id == job_id
    assert loaded.title == "Persist me"
    assert loaded.description == "body"
    assert loaded.status is JobStatus.READY
    assert loaded.created_at == T0
    assert loaded.updated_at == T1
    assert loaded.created_at.tzinfo is not None
    assert loaded.created_at.utcoffset() == timedelta(0)


def test_workflow_step_and_queue_item_round_trip(db_url: str) -> None:
    job = create_job("Job", created_at=T0)
    step = create_workflow_step(job.id, 0, "Step", "Do it", created_at=T0)
    step.transition_to(WorkflowStepStatus.READY, at=T1)
    item = create_queue_item(job.id, step.id, 0, "Do it", created_at=T0, available_at=T1)
    item.transition_to(QueueItemStatus.READY, at=T1)

    with _reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.workflow_steps.save(step)
        uow.queue_items.save(item)
        uow.commit()

    with _reopen(db_url) as uow:
        steps = uow.workflow_steps.list_for_job(job.id)
        items = uow.queue_items.list_for_job(job.id)
        by_step = uow.queue_items.list_for_workflow_step(step.id)

    assert len(steps) == 1
    assert steps[0].status is WorkflowStepStatus.READY
    assert steps[0].prompt == "Do it"
    assert len(items) == 1
    assert items[0].available_at == T1
    assert items[0].status is QueueItemStatus.READY
    assert by_step[0].id == items[0].id


def test_agent_session_round_trip(db_url: str) -> None:
    session = create_agent_session("example-adapter", "ext-1", created_at=T0)
    session.transition_to(AgentSessionStatus.ACTIVE, at=T1)

    with _reopen(db_url) as uow:
        uow.agent_sessions.save(session)
        uow.commit()

    with _reopen(db_url) as uow:
        loaded = uow.agent_sessions.get(session.id)
        by_ext = uow.agent_sessions.get_by_external("example-adapter", "ext-1")

    assert loaded is not None
    assert loaded.status is AgentSessionStatus.ACTIVE
    assert by_ext is not None
    assert by_ext.id == session.id


def test_waiting_quota_and_terminal_run_attempt_round_trip(db_url: str) -> None:
    job = create_job("Job", created_at=T0)
    step = create_workflow_step(job.id, 0, "Step", "Prompt", created_at=T0)
    item = create_queue_item(job.id, step.id, 0, "Prompt", created_at=T0)
    session = create_agent_session("adapter", "ext", created_at=T0)
    waiting = create_run_attempt(item.id, session.id, 1, created_at=T0)
    waiting.transition_to(RunAttemptStatus.RUNNING, at=T0)
    waiting.transition_to(RunAttemptStatus.WAITING_QUOTA, at=T1)

    with _reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.workflow_steps.save(step)
        uow.queue_items.save(item)
        uow.agent_sessions.save(session)
        uow.run_attempts.save(waiting)
        uow.commit()

    with _reopen(db_url) as uow:
        loaded = uow.run_attempts.get(waiting.id)
        active = uow.run_attempts.get_active_for_queue_item(item.id)

    assert loaded is not None
    assert loaded.status is RunAttemptStatus.WAITING_QUOTA
    assert loaded.started_at == T0
    assert loaded.finished_at is None
    assert active is not None
    assert active.id == waiting.id

    waiting.transition_to(RunAttemptStatus.RUNNING, at=T2)
    waiting.transition_to(RunAttemptStatus.COMPLETED, at=T2)

    with _reopen(db_url) as uow:
        uow.run_attempts.save(waiting)
        uow.commit()

    with _reopen(db_url) as uow:
        terminal = uow.run_attempts.get(waiting.id)
        assert terminal is not None
        assert terminal.status is RunAttemptStatus.COMPLETED
        assert terminal.finished_at == T2
        assert terminal.started_at == T0
        assert uow.run_attempts.get_active_for_queue_item(item.id) is None


def test_utc_datetime_preserved_after_reopen(db_url: str) -> None:
    local = datetime(2026, 9, 22, 4, 0, tzinfo=timezone(timedelta(hours=-4)))
    job = create_job("TZ", created_at=local)

    with _reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.commit()

    with _reopen(db_url) as uow:
        loaded = uow.jobs.get(job.id)

    assert loaded is not None
    assert loaded.created_at == T0
    assert loaded.created_at.utcoffset() == timedelta(0)


def test_foreign_key_enforcement(db_url: str) -> None:
    orphan = create_workflow_step(uuid4(), 0, "Orphan", "Prompt", created_at=T0)
    with _reopen(db_url) as uow:
        # Parent flush happens inside save so SQLite rejects the orphan immediately.
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            uow.workflow_steps.save(orphan)

def test_transaction_rollback(db_url: str) -> None:
    job = create_job("Rollback", created_at=T0)
    with _reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.rollback()

    with _reopen(db_url) as uow:
        assert uow.jobs.get(job.id) is None

    with _reopen(db_url) as uow:
        uow.jobs.save(job)
        # leave without commit
    with _reopen(db_url) as uow:
        assert uow.jobs.get(job.id) is None


def test_duplicate_attempt_number_rejected(db_url: str) -> None:
    job = create_job("Job", created_at=T0)
    step = create_workflow_step(job.id, 0, "Step", "Prompt", created_at=T0)
    item = create_queue_item(job.id, step.id, 0, "Prompt", created_at=T0)
    session = create_agent_session("adapter", "ext", created_at=T0)
    first = create_run_attempt(item.id, session.id, 1, created_at=T0)
    first.transition_to(RunAttemptStatus.RUNNING, at=T0)
    first.transition_to(RunAttemptStatus.FAILED, at=T1, failure_reason="boom")
    duplicate = create_run_attempt(item.id, session.id, 1, created_at=T1)

    with _reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.workflow_steps.save(step)
        uow.queue_items.save(item)
        uow.agent_sessions.save(session)
        uow.run_attempts.save(first)
        uow.commit()

    with _reopen(db_url) as uow:
        with pytest.raises(DomainError, match="attempt_number"):
            uow.run_attempts.save(duplicate)


def test_active_run_attempt_invariant(db_url: str) -> None:
    job = create_job("Job", created_at=T0)
    step = create_workflow_step(job.id, 0, "Step", "Prompt", created_at=T0)
    item = create_queue_item(job.id, step.id, 0, "Prompt", created_at=T0)
    session = create_agent_session("adapter", "ext", created_at=T0)
    first = create_run_attempt(item.id, session.id, 1, created_at=T0)
    first.transition_to(RunAttemptStatus.RUNNING, at=T0)
    first.transition_to(RunAttemptStatus.WAITING_QUOTA, at=T1)
    second = create_run_attempt(item.id, session.id, 2, created_at=T1)

    with _reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.workflow_steps.save(step)
        uow.queue_items.save(item)
        uow.agent_sessions.save(session)
        uow.run_attempts.save(first)
        uow.commit()

    with _reopen(db_url) as uow:
        with pytest.raises(DomainError, match="at most one non-terminal"):
            uow.run_attempts.save(second)

    first.transition_to(RunAttemptStatus.CANCELLED, at=T2)
    with _reopen(db_url) as uow:
        uow.run_attempts.save(first)
        uow.run_attempts.save(second)
        uow.commit()

    with _reopen(db_url) as uow:
        active = uow.run_attempts.get_active_for_queue_item(item.id)
        assert active is not None
        assert active.id == second.id
        assert active.attempt_number == 2
