"""Create TASK-002 domain tables for durable SQLite persistence.

Revision ID: 0001_domain_tables
Revises:
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_domain_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("adapter_id", sa.String(length=128), nullable=False),
        sa.Column("external_session_id", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_sessions")),
        sa.UniqueConstraint(
            "adapter_id",
            "external_session_id",
            name="uq_agent_sessions_adapter_external",
        ),
    )
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_workflow_steps_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_steps")),
        sa.UniqueConstraint("job_id", "sequence", name="uq_workflow_steps_job_sequence"),
    )
    op.create_index(op.f("ix_workflow_steps_job_id"), "workflow_steps", ["job_id"], unique=False)
    op.create_table(
        "queue_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_step_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("available_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_queue_items_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_step_id"],
            ["workflow_steps.id"],
            name=op.f("fk_queue_items_workflow_step_id_workflow_steps"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_queue_items")),
        sa.UniqueConstraint("job_id", "sequence", name="uq_queue_items_job_sequence"),
    )
    op.create_index(op.f("ix_queue_items_job_id"), "queue_items", ["job_id"], unique=False)
    op.create_index(
        op.f("ix_queue_items_workflow_step_id"),
        "queue_items",
        ["workflow_step_id"],
        unique=False,
    )
    op.create_table(
        "run_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("queue_item_id", sa.String(length=36), nullable=False),
        sa.Column("agent_session_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.String(length=32), nullable=True),
        sa.Column("finished_at", sa.String(length=32), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_session_id"],
            ["agent_sessions.id"],
            name=op.f("fk_run_attempts_agent_session_id_agent_sessions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["queue_item_id"],
            ["queue_items.id"],
            name=op.f("fk_run_attempts_queue_item_id_queue_items"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_attempts")),
        sa.UniqueConstraint(
            "queue_item_id",
            "attempt_number",
            name="uq_run_attempts_queue_item_attempt_number",
        ),
    )
    op.create_index(
        op.f("ix_run_attempts_agent_session_id"),
        "run_attempts",
        ["agent_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_run_attempts_queue_item_id"),
        "run_attempts",
        ["queue_item_id"],
        unique=False,
    )
    op.create_index(
        "uq_run_attempts_one_active_per_queue_item",
        "run_attempts",
        ["queue_item_id"],
        unique=True,
        sqlite_where=sa.text("status NOT IN ('completed', 'failed', 'cancelled')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_run_attempts_one_active_per_queue_item",
        table_name="run_attempts",
        sqlite_where=sa.text("status NOT IN ('completed', 'failed', 'cancelled')"),
    )
    op.drop_index(op.f("ix_run_attempts_queue_item_id"), table_name="run_attempts")
    op.drop_index(op.f("ix_run_attempts_agent_session_id"), table_name="run_attempts")
    op.drop_table("run_attempts")
    op.drop_index(op.f("ix_queue_items_workflow_step_id"), table_name="queue_items")
    op.drop_index(op.f("ix_queue_items_job_id"), table_name="queue_items")
    op.drop_table("queue_items")
    op.drop_index(op.f("ix_workflow_steps_job_id"), table_name="workflow_steps")
    op.drop_table("workflow_steps")
    op.drop_table("agent_sessions")
    op.drop_table("jobs")
