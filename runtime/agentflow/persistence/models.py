"""SQLAlchemy ORM models for domain tables.

These models are persistence-only. Domain entities remain dataclasses under
``agentflow.core.domain`` and are mapped explicitly in ``mappers``.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, MetaData, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agentflow.persistence.types import UtcDateTimeAsIso, UuidAsString

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(UuidAsString(), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTimeAsIso(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTimeAsIso(), nullable=False)


class WorkflowStepRow(Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_workflow_steps_job_sequence"),
    )

    id: Mapped[UUID] = mapped_column(UuidAsString(), primary_key=True)
    job_id: Mapped[UUID] = mapped_column(
        UuidAsString(),
        ForeignKey("jobs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTimeAsIso(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTimeAsIso(), nullable=False)


class QueueItemRow(Base):
    __tablename__ = "queue_items"
    __table_args__ = (UniqueConstraint("job_id", "sequence", name="uq_queue_items_job_sequence"),)

    id: Mapped[UUID] = mapped_column(UuidAsString(), primary_key=True)
    job_id: Mapped[UUID] = mapped_column(
        UuidAsString(),
        ForeignKey("jobs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    workflow_step_id: Mapped[UUID] = mapped_column(
        UuidAsString(),
        ForeignKey("workflow_steps.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTimeAsIso(), nullable=False)
    available_at: Mapped[datetime] = mapped_column(UtcDateTimeAsIso(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTimeAsIso(), nullable=False)


class AgentSessionRow(Base):
    __tablename__ = "agent_sessions"
    __table_args__ = (
        UniqueConstraint(
            "adapter_id",
            "external_session_id",
            name="uq_agent_sessions_adapter_external",
        ),
    )

    id: Mapped[UUID] = mapped_column(UuidAsString(), primary_key=True)
    adapter_id: Mapped[str] = mapped_column(String(128), nullable=False)
    external_session_id: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTimeAsIso(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTimeAsIso(), nullable=False)


class RunAttemptRow(Base):
    __tablename__ = "run_attempts"
    __table_args__ = (
        UniqueConstraint(
            "queue_item_id",
            "attempt_number",
            name="uq_run_attempts_queue_item_attempt_number",
        ),
        # At most one non-terminal attempt per queue item. Quota waits resume
        # the same row; a replacement attempt requires the previous one to end.
        Index(
            "uq_run_attempts_one_active_per_queue_item",
            "queue_item_id",
            unique=True,
            sqlite_where=text("status NOT IN ('completed', 'failed', 'cancelled')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(UuidAsString(), primary_key=True)
    queue_item_id: Mapped[UUID] = mapped_column(
        UuidAsString(),
        ForeignKey("queue_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    agent_session_id: Mapped[UUID] = mapped_column(
        UuidAsString(),
        ForeignKey("agent_sessions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTimeAsIso(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTimeAsIso(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTimeAsIso(), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
