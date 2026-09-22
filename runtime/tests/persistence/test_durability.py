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
from agentflow.core.events import JOB_CREATED, RUN_ATTEMPT_STATUS_CHANGED, create_runtime_event
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from tests.persistence.helpers import HEAD_REVISION, migrate_down, migrate_to, reopen

T0 = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
T1 = datetime(2026, 9, 22, 8, 5, tzinfo=UTC)
T2 = datetime(2026, 9, 22, 8, 10, tzinfo=UTC)


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    path = tmp_path / "agentflow.db"
    migrate_to(path)
    return f"sqlite:///{path.as_posix()}"


def _version(db_path: Path) -> str | None:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        return None if row is None else row[0]


def test_alembic_revision_is_recorded(tmp_path: Path) -> None:
    path = tmp_path / "migrated.db"
    migrate_to(path)
    assert _version(path) == HEAD_REVISION
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
    assert {
        "jobs",
        "workflow_steps",
        "queue_items",
        "agent_sessions",
        "run_attempts",
        "runtime_events",
        "alembic_version",
    } <= tables


def test_alembic_upgrade_head_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "idempotent.db"
    migrate_to(path)
    assert _version(path) == HEAD_REVISION
    migrate_to(path)
    assert _version(path) == HEAD_REVISION


def test_alembic_downgrade_and_reupgrade(tmp_path: Path) -> None:
    path = tmp_path / "cycle.db"
    migrate_to(path)
    assert _version(path) == HEAD_REVISION
    migrate_down(path, "base")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
    assert "jobs" not in tables
    assert "runtime_events" not in tables
    migrate_to(path)
    assert _version(path) == HEAD_REVISION


def test_job_round_trip_survives_close_reopen(db_url: str) -> None:
    job = create_job("Persist me", "body", created_at=T0)
    job.transition_to(JobStatus.READY, at=T1)
    job_id = job.id

    with reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.commit()

    with reopen(db_url) as uow:
        loaded = uow.jobs.get(job_id)

    assert loaded is not None
    assert loaded.status is JobStatus.READY
    assert loaded.created_at == T0
    assert loaded.updated_at == T1
    assert loaded.created_at.utcoffset() == timedelta(0)


def test_workflow_step_and_queue_item_round_trip(db_url: str) -> None:
    job = create_job("Job", created_at=T0)
    step = create_workflow_step(job.id, 0, "Step", "Do it", created_at=T0)
    step.transition_to(WorkflowStepStatus.READY, at=T1)
    item = create_queue_item(job.id, step.id, 0, "Do it", created_at=T0, available_at=T1)
    item.transition_to(QueueItemStatus.READY, at=T1)

    with reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.workflow_steps.save(step)
        uow.queue_items.save(item)
        uow.commit()

    with reopen(db_url) as uow:
        steps = uow.workflow_steps.list_for_job(job.id)
        items = uow.queue_items.list_for_job(job.id)

    assert steps[0].status is WorkflowStepStatus.READY
    assert items[0].available_at == T1


def test_agent_session_round_trip(db_url: str) -> None:
    session = create_agent_session("example-adapter", "ext-1", created_at=T0)
    session.transition_to(AgentSessionStatus.ACTIVE, at=T1)
    with reopen(db_url) as uow:
        uow.agent_sessions.save(session)
        uow.commit()
    with reopen(db_url) as uow:
        loaded = uow.agent_sessions.get_by_external("example-adapter", "ext-1")
    assert loaded is not None
    assert loaded.status is AgentSessionStatus.ACTIVE


def test_waiting_quota_and_terminal_run_attempt_round_trip(db_url: str) -> None:
    job = create_job("Job", created_at=T0)
    step = create_workflow_step(job.id, 0, "Step", "Prompt", created_at=T0)
    item = create_queue_item(job.id, step.id, 0, "Prompt", created_at=T0)
    session = create_agent_session("adapter", "ext", created_at=T0)
    waiting = create_run_attempt(item.id, session.id, 1, created_at=T0)
    waiting.transition_to(RunAttemptStatus.RUNNING, at=T0)
    waiting.transition_to(RunAttemptStatus.WAITING_QUOTA, at=T1)

    with reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.workflow_steps.save(step)
        uow.queue_items.save(item)
        uow.agent_sessions.save(session)
        uow.run_attempts.save(waiting)
        uow.commit()

    with reopen(db_url) as uow:
        loaded = uow.run_attempts.get(waiting.id)
        assert loaded is not None
        assert loaded.status is RunAttemptStatus.WAITING_QUOTA
        assert loaded.updated_at == T1
        assert uow.run_attempts.get_active_for_queue_item(item.id) is not None

    waiting.transition_to(RunAttemptStatus.RUNNING, at=T2)
    waiting.transition_to(RunAttemptStatus.COMPLETED, at=T2)
    with reopen(db_url) as uow:
        uow.run_attempts.save(waiting)
        uow.commit()
    with reopen(db_url) as uow:
        terminal = uow.run_attempts.get(waiting.id)
        assert terminal is not None
        assert terminal.status is RunAttemptStatus.COMPLETED
        assert terminal.updated_at == T2
        assert terminal.finished_at == T2


def test_utc_datetime_preserved_after_reopen(db_url: str) -> None:
    local = datetime(2026, 9, 22, 4, 0, tzinfo=timezone(timedelta(hours=-4)))
    job = create_job("TZ", created_at=local)
    with reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.commit()
    with reopen(db_url) as uow:
        loaded = uow.jobs.get(job.id)
    assert loaded is not None
    assert loaded.created_at == T0


def test_foreign_key_enforcement(db_url: str) -> None:
    orphan = create_workflow_step(uuid4(), 0, "Orphan", "Prompt", created_at=T0)
    with reopen(db_url) as uow:
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            uow.workflow_steps.save(orphan)


def test_transaction_rollback(db_url: str) -> None:
    job = create_job("Rollback", created_at=T0)
    with reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.rollback()
    with reopen(db_url) as uow:
        assert uow.jobs.get(job.id) is None
    with reopen(db_url) as uow:
        uow.jobs.save(job)
    with reopen(db_url) as uow:
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

    with reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.workflow_steps.save(step)
        uow.queue_items.save(item)
        uow.agent_sessions.save(session)
        uow.run_attempts.save(first)
        uow.commit()

    with reopen(db_url) as uow:
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

    with reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.workflow_steps.save(step)
        uow.queue_items.save(item)
        uow.agent_sessions.save(session)
        uow.run_attempts.save(first)
        uow.commit()

    with reopen(db_url) as uow:
        with pytest.raises(DomainError, match="at most one non-terminal"):
            uow.run_attempts.save(second)

    first.transition_to(RunAttemptStatus.CANCELLED, at=T2)
    with reopen(db_url) as uow:
        uow.run_attempts.save(first)
        uow.run_attempts.save(second)
        uow.commit()

    with reopen(db_url) as uow:
        active = uow.run_attempts.get_active_for_queue_item(item.id)
        assert active is not None
        assert active.id == second.id


def test_cross_job_queue_item_is_rejected(db_url: str) -> None:
    job_a = create_job("A", created_at=T0)
    job_b = create_job("B", created_at=T0)
    step_b = create_workflow_step(job_b.id, 0, "Step B", "Prompt", created_at=T0)
    crossed = create_queue_item(job_a.id, step_b.id, 0, "Prompt", created_at=T0)

    with reopen(db_url) as uow:
        uow.jobs.save(job_a)
        uow.jobs.save(job_b)
        uow.workflow_steps.save(step_b)
        with pytest.raises(DomainError, match="job_id"):
            uow.queue_items.save(crossed)
        uow.commit()


def test_repository_constraint_error_does_not_rollback_unrelated_uow_work(db_url: str) -> None:
    job = create_job("Keep me", created_at=T0)
    step = create_workflow_step(job.id, 0, "Step", "Prompt", created_at=T0)
    item = create_queue_item(job.id, step.id, 0, "Prompt", created_at=T0)
    session = create_agent_session("adapter", "ext", created_at=T0)
    first = create_run_attempt(item.id, session.id, 1, created_at=T0)
    first.transition_to(RunAttemptStatus.RUNNING, at=T0)
    first.transition_to(RunAttemptStatus.FAILED, at=T1, failure_reason="boom")
    duplicate = create_run_attempt(item.id, session.id, 1, created_at=T1)
    survivor = create_job("Survivor", created_at=T1)

    with reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.workflow_steps.save(step)
        uow.queue_items.save(item)
        uow.agent_sessions.save(session)
        uow.run_attempts.save(first)
        uow.commit()

    with reopen(db_url) as uow:
        uow.jobs.save(survivor)
        with pytest.raises(DomainError, match="attempt_number"):
            uow.run_attempts.save(duplicate)
        uow.commit()

    with reopen(db_url) as uow:
        assert uow.jobs.get(survivor.id) is not None


def test_naive_persisted_timestamp_is_rejected(db_url: str) -> None:
    job = create_job("Corrupt me", created_at=T0)
    with reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.commit()

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE jobs SET created_at = :ts WHERE id = :id"),
            {"ts": "2026-09-22T08:00:00", "id": str(job.id)},
        )

    with reopen(db_url) as uow:
        with pytest.raises(ValueError, match="timezone"):
            uow.jobs.get(job.id)


def test_default_database_parent_is_created(tmp_path: Path) -> None:
    nested = tmp_path / "missing" / "nested" / "agentflow.db"
    assert not nested.parent.exists()
    url = f"sqlite:///{nested.as_posix()}"
    from agentflow.persistence.database import create_sqlite_engine

    engine = create_sqlite_engine(url)
    assert nested.parent.is_dir()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def test_state_change_and_event_commit_atomically(db_url: str) -> None:
    job = create_job("Atomic", created_at=T0)
    event = create_runtime_event(
        JOB_CREATED,
        job_id=job.id,
        aggregate_type="job",
        aggregate_id=job.id,
        payload={"title": job.title},
        occurred_at=T0,
    )
    with reopen(db_url) as uow:
        uow.jobs.save(job)
        stored = uow.events.append(event)
        uow.commit()
        assert stored.position >= 1

    with reopen(db_url) as uow:
        assert uow.jobs.get(job.id) is not None
        assert uow.events.get(event.id) is not None


def test_state_change_and_event_rollback_atomically(db_url: str) -> None:
    job = create_job("Rollback both", created_at=T0)
    event = create_runtime_event(
        RUN_ATTEMPT_STATUS_CHANGED,
        job_id=job.id,
        payload={"to": "running"},
        occurred_at=T0,
    )
    with reopen(db_url) as uow:
        uow.jobs.save(job)
        uow.events.append(event)
        uow.rollback()

    with reopen(db_url) as uow:
        assert uow.jobs.get(job.id) is None
        assert uow.events.get(event.id) is None
