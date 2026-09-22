"""Legal and illegal lifecycle transitions."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from agentflow.core.domain.agent_session import AgentSession
from agentflow.core.domain.exceptions import DomainError, InvalidStateTransition
from agentflow.core.domain.job import Job
from agentflow.core.domain.queue_item import QueueItem, create_queue_item
from agentflow.core.domain.run_attempt import RunAttempt, create_run_attempt
from agentflow.core.domain.statuses import (
    AgentSessionStatus,
    JobStatus,
    QueueItemStatus,
    RunAttemptStatus,
    WorkflowStepStatus,
    is_recoverable_status,
    is_terminal_status,
)
from agentflow.core.domain.transitions import (
    AGENT_SESSION_TRANSITIONS,
    JOB_TRANSITIONS,
    QUEUE_ITEM_TRANSITIONS,
    RUN_ATTEMPT_TRANSITIONS,
    WORKFLOW_STEP_TRANSITIONS,
)
from agentflow.core.domain.workflow_step import WorkflowStep

T0 = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
T1 = datetime(2026, 9, 21, 12, 5, tzinfo=UTC)
T2 = datetime(2026, 9, 21, 12, 10, tzinfo=UTC)
T3 = datetime(2026, 9, 21, 12, 15, tzinfo=UTC)


def _pairs(table: dict, *, legal: bool) -> list[tuple]:
    cases = []
    for current, allowed in table.items():
        for target in table:
            if (target in allowed) is legal:
                cases.append((current, target))
    return cases


def _job(status: JobStatus) -> Job:
    return Job(
        id=uuid4(),
        title="Implement feature",
        description="",
        created_at=T0,
        updated_at=T0,
        status=status,
    )


def _step(status: WorkflowStepStatus) -> WorkflowStep:
    return WorkflowStep(
        id=uuid4(),
        job_id=uuid4(),
        sequence=1,
        title="Run tests",
        prompt="Run the suite",
        created_at=T0,
        updated_at=T0,
        status=status,
    )


def _item(status: QueueItemStatus) -> QueueItem:
    return QueueItem(
        id=uuid4(),
        job_id=uuid4(),
        workflow_step_id=uuid4(),
        sequence=1,
        prompt="Dispatch the step",
        created_at=T0,
        available_at=T0,
        updated_at=T0,
        status=status,
    )


def _session(status: AgentSessionStatus) -> AgentSession:
    return AgentSession(
        id=uuid4(),
        adapter_id="example-adapter",
        external_session_id="external-1",
        created_at=T0,
        updated_at=T0,
        status=status,
    )


def _attempt(status: RunAttemptStatus) -> RunAttempt:
    """Build a RunAttempt already in ``status`` with consistent timestamps."""
    started: datetime | None
    finished: datetime | None
    if status is RunAttemptStatus.CREATED:
        started = None
        finished = None
    elif status is RunAttemptStatus.CANCELLED:
        # Cancellation before start is a valid terminal path.
        started = None
        finished = T0
    elif is_terminal_status(status):
        started = T0
        finished = T0
    else:
        started = T0
        finished = None
    return RunAttempt(
        id=uuid4(),
        queue_item_id=uuid4(),
        agent_session_id=uuid4(),
        attempt_number=1,
        created_at=T0,
        updated_at=T0,
        started_at=started,
        finished_at=finished,
        status=status,
    )


@pytest.mark.parametrize(("current", "target"), _pairs(JOB_TRANSITIONS, legal=True))
def test_legal_job_transitions(current: JobStatus, target: JobStatus) -> None:
    job = _job(current)
    job.transition_to(target, at=T1)
    assert job.status is target
    assert job.updated_at == T1


@pytest.mark.parametrize(("current", "target"), _pairs(JOB_TRANSITIONS, legal=False))
def test_illegal_job_transitions(current: JobStatus, target: JobStatus) -> None:
    job = _job(current)
    with pytest.raises(InvalidStateTransition) as caught:
        job.transition_to(target, at=T1)
    assert job.status is current
    assert job.updated_at == T0
    assert caught.value.entity == "Job"
    assert caught.value.current == current.value
    assert caught.value.target == target.value


@pytest.mark.parametrize(("current", "target"), _pairs(WORKFLOW_STEP_TRANSITIONS, legal=True))
def test_legal_workflow_step_transitions(
    current: WorkflowStepStatus,
    target: WorkflowStepStatus,
) -> None:
    step = _step(current)
    step.transition_to(target, at=T1)
    assert step.status is target
    assert step.updated_at == T1


@pytest.mark.parametrize(("current", "target"), _pairs(WORKFLOW_STEP_TRANSITIONS, legal=False))
def test_illegal_workflow_step_transitions(
    current: WorkflowStepStatus,
    target: WorkflowStepStatus,
) -> None:
    step = _step(current)
    with pytest.raises(InvalidStateTransition):
        step.transition_to(target, at=T1)
    assert step.status is current
    assert step.updated_at == T0


@pytest.mark.parametrize(("current", "target"), _pairs(QUEUE_ITEM_TRANSITIONS, legal=True))
def test_legal_queue_item_transitions(
    current: QueueItemStatus,
    target: QueueItemStatus,
) -> None:
    item = _item(current)
    item.transition_to(target, at=T1)
    assert item.status is target
    assert item.updated_at == T1


@pytest.mark.parametrize(("current", "target"), _pairs(QUEUE_ITEM_TRANSITIONS, legal=False))
def test_illegal_queue_item_transitions(
    current: QueueItemStatus,
    target: QueueItemStatus,
) -> None:
    item = _item(current)
    with pytest.raises(InvalidStateTransition):
        item.transition_to(target, at=T1)
    assert item.status is current
    assert item.updated_at == T0


@pytest.mark.parametrize(("current", "target"), _pairs(AGENT_SESSION_TRANSITIONS, legal=True))
def test_legal_agent_session_transitions(
    current: AgentSessionStatus,
    target: AgentSessionStatus,
) -> None:
    session = _session(current)
    session.transition_to(target, at=T1)
    assert session.status is target
    assert session.updated_at == T1


@pytest.mark.parametrize(("current", "target"), _pairs(AGENT_SESSION_TRANSITIONS, legal=False))
def test_illegal_agent_session_transitions(
    current: AgentSessionStatus,
    target: AgentSessionStatus,
) -> None:
    session = _session(current)
    with pytest.raises(InvalidStateTransition):
        session.transition_to(target, at=T1)
    assert session.status is current
    assert session.updated_at == T0


@pytest.mark.parametrize(("current", "target"), _pairs(RUN_ATTEMPT_TRANSITIONS, legal=True))
def test_legal_run_attempt_transitions(
    current: RunAttemptStatus,
    target: RunAttemptStatus,
) -> None:
    attempt = _attempt(current)
    attempt.transition_to(target, at=T1)
    assert attempt.status is target


@pytest.mark.parametrize(("current", "target"), _pairs(RUN_ATTEMPT_TRANSITIONS, legal=False))
def test_illegal_run_attempt_transitions(
    current: RunAttemptStatus,
    target: RunAttemptStatus,
) -> None:
    attempt = _attempt(current)
    with pytest.raises(InvalidStateTransition):
        attempt.transition_to(target, at=T1)
    assert attempt.status is current


@pytest.mark.parametrize(
    "terminal",
    [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED],
)
def test_terminal_job_cannot_return_to_running(terminal: JobStatus) -> None:
    job = _job(terminal)
    with pytest.raises(InvalidStateTransition):
        job.transition_to(JobStatus.RUNNING, at=T1)
    assert job.status is terminal


@pytest.mark.parametrize(
    "terminal",
    [QueueItemStatus.COMPLETED, QueueItemStatus.FAILED, QueueItemStatus.CANCELLED],
)
def test_terminal_queue_item_cannot_return_to_running(terminal: QueueItemStatus) -> None:
    item = _item(terminal)
    with pytest.raises(InvalidStateTransition):
        item.transition_to(QueueItemStatus.RUNNING, at=T1)
    assert item.status is terminal


@pytest.mark.parametrize(
    "terminal",
    [RunAttemptStatus.COMPLETED, RunAttemptStatus.FAILED, RunAttemptStatus.CANCELLED],
)
def test_terminal_run_attempt_cannot_return_to_running(terminal: RunAttemptStatus) -> None:
    attempt = _attempt(terminal)
    with pytest.raises(InvalidStateTransition):
        attempt.transition_to(RunAttemptStatus.RUNNING, at=T1)
    assert attempt.status is terminal


def test_job_quota_interruption_can_return_to_ready_or_running() -> None:
    job = _job(JobStatus.CREATED)
    job.transition_to(JobStatus.READY, at=T0)
    job.transition_to(JobStatus.RUNNING, at=T0)
    job.transition_to(JobStatus.WAITING_QUOTA, at=T1)

    assert job.status is JobStatus.WAITING_QUOTA
    assert is_recoverable_status(job.status)
    assert not is_terminal_status(job.status)

    job.transition_to(JobStatus.READY, at=T2)
    job.transition_to(JobStatus.RUNNING, at=T2)
    job.transition_to(JobStatus.WAITING_QUOTA, at=T2)
    job.transition_to(JobStatus.RUNNING, at=T3)
    assert job.status is JobStatus.RUNNING


def test_queue_item_quota_interruption_can_return_to_ready_or_running() -> None:
    item = create_queue_item(uuid4(), uuid4(), 1, "Prompt", created_at=T0)
    item.transition_to(QueueItemStatus.READY, at=T0)
    item.transition_to(QueueItemStatus.RUNNING, at=T0)
    item.transition_to(QueueItemStatus.WAITING_QUOTA, at=T1)

    assert is_recoverable_status(item.status)
    assert not is_terminal_status(item.status)
    assert item.status is not QueueItemStatus.FAILED

    resumed = _item(QueueItemStatus.WAITING_QUOTA)
    resumed.transition_to(QueueItemStatus.RUNNING, at=T2)
    assert resumed.status is QueueItemStatus.RUNNING


def test_run_attempt_quota_interruption_resumes_without_becoming_failure() -> None:
    attempt = create_run_attempt(uuid4(), uuid4(), 1, created_at=T0)
    attempt.transition_to(RunAttemptStatus.RUNNING, at=T0)
    attempt.transition_to(RunAttemptStatus.WAITING_QUOTA, at=T1)

    assert attempt.status is RunAttemptStatus.WAITING_QUOTA
    assert attempt.started_at == T0
    assert attempt.finished_at is None
    assert attempt.failure_reason is None
    assert is_recoverable_status(attempt.status)
    assert not is_terminal_status(attempt.status)

    with pytest.raises(InvalidStateTransition):
        attempt.transition_to(RunAttemptStatus.FAILED, at=T2, failure_reason="quota")

    assert attempt.status is RunAttemptStatus.WAITING_QUOTA
    attempt.transition_to(RunAttemptStatus.RUNNING, at=T3)
    assert attempt.status is RunAttemptStatus.RUNNING
    assert attempt.started_at == T0
    assert attempt.finished_at is None


def test_later_attempt_can_fail_or_complete_after_an_interrupted_attempt() -> None:
    queue_item_id = uuid4()
    session_id = uuid4()
    interrupted = create_run_attempt(queue_item_id, session_id, 1, created_at=T0)
    interrupted.transition_to(RunAttemptStatus.RUNNING, at=T0)
    interrupted.transition_to(RunAttemptStatus.WAITING_QUOTA, at=T1)

    failed = create_run_attempt(queue_item_id, session_id, 2, created_at=T1)
    failed.transition_to(RunAttemptStatus.RUNNING, at=T1)
    failed.transition_to(RunAttemptStatus.FAILED, at=T2, failure_reason="network unreachable")

    succeeded = create_run_attempt(queue_item_id, session_id, 3, created_at=T2)
    succeeded.transition_to(RunAttemptStatus.RUNNING, at=T2)
    succeeded.transition_to(RunAttemptStatus.COMPLETED, at=T3)

    assert interrupted.status is RunAttemptStatus.WAITING_QUOTA
    assert failed.status is RunAttemptStatus.FAILED
    assert failed.failure_reason == "network unreachable"
    assert failed.finished_at == T2
    assert succeeded.status is RunAttemptStatus.COMPLETED
    assert succeeded.finished_at == T3
    assert succeeded.failure_reason is None


def test_failure_reason_is_rejected_unless_the_attempt_fails() -> None:
    attempt = create_run_attempt(uuid4(), uuid4(), 1, created_at=T0)
    attempt.transition_to(RunAttemptStatus.RUNNING, at=T0)
    with pytest.raises(DomainError, match="failure_reason"):
        attempt.transition_to(
            RunAttemptStatus.COMPLETED,
            at=T1,
            failure_reason="should not be recorded",
        )
    assert attempt.status is RunAttemptStatus.RUNNING
    assert attempt.finished_at is None


def test_blank_failure_reason_does_not_complete_the_transition() -> None:
    attempt = create_run_attempt(uuid4(), uuid4(), 1, created_at=T0)
    attempt.transition_to(RunAttemptStatus.RUNNING, at=T0)
    with pytest.raises(DomainError, match="failure_reason"):
        attempt.transition_to(RunAttemptStatus.FAILED, at=T1, failure_reason="  ")
    assert attempt.status is RunAttemptStatus.RUNNING
    assert attempt.finished_at is None


def test_agent_session_quota_wait_resumes_to_active() -> None:
    session = _session(AgentSessionStatus.CREATED)
    session.transition_to(AgentSessionStatus.ACTIVE, at=T0)
    session.transition_to(AgentSessionStatus.WAITING_QUOTA, at=T1)
    assert is_recoverable_status(session.status)
    assert not is_terminal_status(session.status)
    session.transition_to(AgentSessionStatus.ACTIVE, at=T2)
    assert session.status is AgentSessionStatus.ACTIVE


def test_status_cannot_be_assigned_directly() -> None:
    job = _job(JobStatus.CREATED)
    with pytest.raises(DomainError, match="transition_to"):
        job.status = JobStatus.RUNNING
    assert job.status is JobStatus.CREATED


def test_transition_rejects_a_status_from_another_entity() -> None:
    job = _job(JobStatus.CREATED)
    with pytest.raises(DomainError, match="JobStatus"):
        job.transition_to(RunAttemptStatus.RUNNING, at=T1)  # type: ignore[arg-type]
    assert job.status is JobStatus.CREATED


def test_updated_at_before_created_at_is_rejected() -> None:
    with pytest.raises(DomainError, match="updated_at"):
        Job(
            id=uuid4(),
            title="Title",
            description="",
            created_at=T1,
            updated_at=T0,
        )


def test_available_at_before_created_at_is_rejected() -> None:
    with pytest.raises(DomainError, match="available_at"):
        QueueItem(
            id=uuid4(),
            job_id=uuid4(),
            workflow_step_id=uuid4(),
            sequence=0,
            prompt="Prompt",
            created_at=T1,
            available_at=T0,
            updated_at=T1,
        )


def test_transition_must_not_move_timestamps_backwards() -> None:
    job = _job(JobStatus.CREATED)
    job.transition_to(JobStatus.READY, at=T1)
    with pytest.raises(DomainError, match="transition time"):
        job.transition_to(JobStatus.RUNNING, at=T0)
    assert job.status is JobStatus.READY
    assert job.updated_at == T1


@pytest.mark.parametrize(
    ("status", "kwargs", "match"),
    [
        (
            RunAttemptStatus.CREATED,
            {"finished_at": T0},
            "CREATED",
        ),
        (
            RunAttemptStatus.RUNNING,
            {"started_at": T0, "finished_at": T0},
            "finished_at",
        ),
        (
            RunAttemptStatus.COMPLETED,
            {"started_at": T0},
            "finished_at",
        ),
        (
            RunAttemptStatus.FAILED,
            {"started_at": T0},
            "finished_at",
        ),
        (
            RunAttemptStatus.WAITING_QUOTA,
            {},
            "started_at",
        ),
        (
            RunAttemptStatus.WAITING_USER,
            {},
            "started_at",
        ),
        (
            RunAttemptStatus.PAUSED,
            {},
            "started_at",
        ),
        (
            RunAttemptStatus.RUNNING,
            {"started_at": T0, "failure_reason": "nope"},
            "failure_reason",
        ),
    ],
)
def test_run_attempt_rejects_inconsistent_reconstruction(
    status: RunAttemptStatus,
    kwargs: dict,
    match: str,
) -> None:
    with pytest.raises(DomainError, match=match):
        RunAttempt(
            id=uuid4(),
            queue_item_id=uuid4(),
            agent_session_id=uuid4(),
            attempt_number=1,
            created_at=T0,
            updated_at=T0,
            status=status,
            **kwargs,
        )


def test_cancelled_before_start_is_valid() -> None:
    attempt = RunAttempt(
        id=uuid4(),
        queue_item_id=uuid4(),
        agent_session_id=uuid4(),
        attempt_number=1,
        created_at=T0,
        updated_at=T1,
        finished_at=T1,
        status=RunAttemptStatus.CANCELLED,
    )
    assert attempt.started_at is None
    assert attempt.finished_at == T1


def test_failed_without_failure_reason_is_allowed() -> None:
    attempt = RunAttempt(
        id=uuid4(),
        queue_item_id=uuid4(),
        agent_session_id=uuid4(),
        attempt_number=1,
        created_at=T0,
        updated_at=T1,
        started_at=T0,
        finished_at=T1,
        status=RunAttemptStatus.FAILED,
    )
    assert attempt.failure_reason is None


def test_run_attempt_cannot_resume_before_previous_transition() -> None:
    attempt = create_run_attempt(uuid4(), uuid4(), 1, created_at=T0)
    attempt.transition_to(RunAttemptStatus.RUNNING, at=T0)
    attempt.transition_to(RunAttemptStatus.WAITING_QUOTA, at=T2)
    with pytest.raises(DomainError, match="updated_at"):
        attempt.transition_to(RunAttemptStatus.RUNNING, at=T1)
    assert attempt.status is RunAttemptStatus.WAITING_QUOTA
    assert attempt.updated_at == T2
