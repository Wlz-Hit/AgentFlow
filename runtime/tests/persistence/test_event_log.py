"""Durable runtime event log integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from agentflow.core.domain.exceptions import DomainError
from agentflow.core.events import (
    JOB_CREATED,
    JOB_STATUS_CHANGED,
    QUEUE_ITEM_ENQUEUED,
    create_runtime_event,
)
from sqlalchemy import create_engine

from tests.persistence.helpers import migrate_to, reopen

T0 = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)
T1 = datetime(2026, 9, 22, 9, 5, tzinfo=UTC)


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    path = tmp_path / "events.db"
    migrate_to(path)
    return f"sqlite:///{path.as_posix()}"


def test_event_round_trip_survives_close_reopen(db_url: str) -> None:
    job_id = uuid4()
    correlation = uuid4()
    causation = uuid4()
    event = create_runtime_event(
        JOB_CREATED,
        job_id=job_id,
        aggregate_type="job",
        aggregate_id=job_id,
        payload={"title": "Ship it", "count": 2},
        correlation_id=correlation,
        causation_id=causation,
        occurred_at=T0,
    )
    with reopen(db_url) as uow:
        stored = uow.events.append(event)
        uow.commit()
        position = stored.position

    with reopen(db_url) as uow:
        loaded = uow.events.get(event.id)

    assert loaded is not None
    assert loaded.position == position
    assert loaded.event.event_type == JOB_CREATED
    assert loaded.event.payload == {"count": 2, "title": "Ship it"}
    assert loaded.event.correlation_id == correlation
    assert loaded.event.causation_id == causation
    assert loaded.event.occurred_at == T0
    assert loaded.event.occurred_at.utcoffset() == timedelta(0)


def test_event_positions_increase_and_list_after(db_url: str) -> None:
    job_id = uuid4()
    events = [
        create_runtime_event(JOB_CREATED, job_id=job_id, payload={"n": 1}, occurred_at=T0),
        create_runtime_event(JOB_STATUS_CHANGED, job_id=job_id, payload={"n": 2}, occurred_at=T1),
        create_runtime_event(QUEUE_ITEM_ENQUEUED, job_id=job_id, payload={"n": 3}, occurred_at=T1),
    ]
    with reopen(db_url) as uow:
        positions = [uow.events.append(event).position for event in events]
        uow.commit()

    assert positions == sorted(positions)
    assert positions[0] < positions[1] < positions[2]

    with reopen(db_url) as uow:
        newer = uow.events.list_after(positions[0])
        for_job = uow.events.list_for_job(job_id)

    assert [item.event.payload["n"] for item in newer] == [2, 3]
    assert [item.position for item in for_job] == positions


def test_duplicate_event_id_rejected(db_url: str) -> None:
    event_id = uuid4()
    first = create_runtime_event(JOB_CREATED, event_id=event_id, payload={"a": 1}, occurred_at=T0)
    second = create_runtime_event(JOB_CREATED, event_id=event_id, payload={"a": 2}, occurred_at=T1)
    with reopen(db_url) as uow:
        uow.events.append(first)
        with pytest.raises(DomainError, match="event_id"):
            uow.events.append(second)
        uow.commit()

    with reopen(db_url) as uow:
        loaded = uow.events.get(event_id)
    assert loaded is not None
    assert loaded.event.payload == {"a": 1}


def test_append_order_survives_restart(db_url: str) -> None:
    with reopen(db_url) as uow:
        for index in range(5):
            uow.events.append(
                create_runtime_event(
                    JOB_STATUS_CHANGED,
                    payload={"index": index},
                    occurred_at=T0,
                )
            )
        uow.commit()

    engine = create_engine(db_url)
    engine.dispose()

    with reopen(db_url) as uow:
        rows = uow.events.list_after(0)
    assert [row.event.payload["index"] for row in rows] == [0, 1, 2, 3, 4]
    assert [row.position for row in rows] == sorted(row.position for row in rows)


def test_non_json_payload_rejected() -> None:
    with pytest.raises(DomainError, match="JSON-serializable"):
        create_runtime_event(JOB_CREATED, payload={"bad": object()})
