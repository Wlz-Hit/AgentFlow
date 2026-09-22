"""Construction, defaults, and timestamp rules for domain entities."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from agentflow.core.domain import (
    AgentSessionStatus,
    JobStatus,
    QueueItemStatus,
    RunAttemptStatus,
    WorkflowStepStatus,
    create_agent_session,
    create_job,
    create_queue_item,
    create_run_attempt,
    create_workflow_step,
)
from agentflow.core.domain.exceptions import DomainError
from agentflow.core.domain.time import utc_now

T0 = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
JOB_ID = uuid4()
STEP_ID = uuid4()
ITEM_ID = uuid4()
SESSION_ID = uuid4()


def test_create_job_starts_created_with_utc_timestamps() -> None:
    before = utc_now()
    job = create_job("Implement feature", "Add the domain model")
    after = utc_now()

    assert isinstance(job.id, UUID)
    assert job.title == "Implement feature"
    assert job.description == "Add the domain model"
    assert job.status is JobStatus.CREATED
    assert job.created_at.tzinfo is not None
    assert job.created_at.utcoffset() == timedelta(0)
    assert job.updated_at == job.created_at
    assert before <= job.created_at <= after


def test_create_job_description_may_be_empty() -> None:
    job = create_job("Title only", created_at=T0)
    assert job.description == ""
    assert job.created_at == T0
    assert job.updated_at == T0


def test_create_workflow_step_starts_created() -> None:
    step = create_workflow_step(
        JOB_ID,
        1,
        "Run tests",
        "Run the runtime test suite",
        created_at=T0,
    )

    assert isinstance(step.id, UUID)
    assert step.job_id == JOB_ID
    assert step.sequence == 1
    assert step.title == "Run tests"
    assert step.prompt == "Run the runtime test suite"
    assert step.status is WorkflowStepStatus.CREATED
    assert step.created_at == T0
    assert step.updated_at == T0
    assert step.created_at.utcoffset() == timedelta(0)


def test_create_queue_item_is_distinct_from_a_workflow_step() -> None:
    available = datetime(2026, 9, 21, 13, 0, tzinfo=UTC)
    item = create_queue_item(
        JOB_ID,
        STEP_ID,
        2,
        "Dispatch the test step",
        item_id=ITEM_ID,
        created_at=T0,
        available_at=available,
    )

    assert item.id == ITEM_ID
    assert item.job_id == JOB_ID
    assert item.workflow_step_id == STEP_ID
    assert item.sequence == 2
    assert item.prompt == "Dispatch the test step"
    assert item.status is QueueItemStatus.CREATED
    assert item.created_at == T0
    assert item.available_at == available
    assert item.updated_at == T0
    assert type(item).__name__ == "QueueItem"


def test_queue_item_is_available_at_creation_when_unspecified() -> None:
    item = create_queue_item(JOB_ID, STEP_ID, 0, "Prompt", created_at=T0)
    assert item.available_at == T0
    assert item.available_at.utcoffset() == timedelta(0)


def test_create_agent_session_keeps_external_id_generic() -> None:
    session = create_agent_session(
        "example-adapter",
        "session-key-from-adapter",
        session_id=SESSION_ID,
        created_at=T0,
    )

    assert session.id == SESSION_ID
    assert session.adapter_id == "example-adapter"
    assert session.external_session_id == "session-key-from-adapter"
    assert session.status is AgentSessionStatus.CREATED
    assert session.created_at == T0
    assert session.updated_at == T0
    assert not hasattr(session, "codex_thread_id")
    assert not hasattr(session, "claude_session_id")


def test_create_run_attempt_starts_created_without_timing() -> None:
    attempt = create_run_attempt(ITEM_ID, SESSION_ID, 1, created_at=T0)

    assert isinstance(attempt.id, UUID)
    assert attempt.queue_item_id == ITEM_ID
    assert attempt.agent_session_id == SESSION_ID
    assert attempt.attempt_number == 1
    assert attempt.status is RunAttemptStatus.CREATED
    assert attempt.created_at == T0
    assert attempt.started_at is None
    assert attempt.finished_at is None
    assert attempt.failure_reason is None
    assert attempt.created_at.utcoffset() == timedelta(0)


def test_one_queue_item_can_own_several_attempts() -> None:
    first = create_run_attempt(ITEM_ID, SESSION_ID, 1, created_at=T0)
    second = create_run_attempt(ITEM_ID, SESSION_ID, 2, created_at=T0)
    third = create_run_attempt(ITEM_ID, SESSION_ID, 3, created_at=T0)

    assert first.queue_item_id == second.queue_item_id == third.queue_item_id
    assert [first.attempt_number, second.attempt_number, third.attempt_number] == [1, 2, 3]
    assert len({first.id, second.id, third.id}) == 3


@pytest.mark.parametrize(
    ("factory", "kwargs"),
    [
        (create_job, {"title": "   ", "created_at": T0}),
        (
            create_workflow_step,
            {
                "job_id": JOB_ID,
                "sequence": 0,
                "title": " ",
                "prompt": "Do the work",
                "created_at": T0,
            },
        ),
        (
            create_queue_item,
            {
                "job_id": JOB_ID,
                "workflow_step_id": STEP_ID,
                "sequence": 0,
                "prompt": " ",
                "created_at": T0,
            },
        ),
        (
            create_agent_session,
            {"adapter_id": " ", "external_session_id": "ext", "created_at": T0},
        ),
    ],
)
def test_blank_required_text_is_rejected(factory, kwargs) -> None:
    with pytest.raises(DomainError):
        factory(**kwargs)


def test_naive_timestamps_are_rejected() -> None:
    naive = datetime(2026, 9, 21, 12, 0)
    with pytest.raises(DomainError, match="timezone-aware"):
        create_job("Title", created_at=naive)


def test_aware_timestamps_are_normalized_to_utc() -> None:
    eastern = timezone(timedelta(hours=-4))
    local = datetime(2026, 9, 21, 8, 0, tzinfo=eastern)
    job = create_job("Title", created_at=local)
    assert job.created_at == T0
    assert job.updated_at == T0


@pytest.mark.parametrize(
    ("factory", "kwargs"),
    [
        (
            create_workflow_step,
            {
                "job_id": JOB_ID,
                "sequence": -1,
                "title": "Step",
                "prompt": "Prompt",
                "created_at": T0,
            },
        ),
        (
            create_queue_item,
            {
                "job_id": JOB_ID,
                "workflow_step_id": STEP_ID,
                "sequence": -1,
                "prompt": "Prompt",
                "created_at": T0,
            },
        ),
        (
            create_run_attempt,
            {
                "queue_item_id": ITEM_ID,
                "agent_session_id": SESSION_ID,
                "attempt_number": 0,
                "created_at": T0,
            },
        ),
    ],
)
def test_invalid_sequence_numbers_are_rejected(factory, kwargs) -> None:
    with pytest.raises(DomainError):
        factory(**kwargs)
