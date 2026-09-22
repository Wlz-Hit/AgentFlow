"""Create append-only runtime_events table.

Revision ID: 0003_event_log
Revises: 0002_persistence_hardening
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_event_log"
down_revision: str | None = "0002_persistence_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_events",
        sa.Column("position", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=True),
        sa.Column("aggregate_id", sa.String(length=36), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("occurred_at", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=True),
        sa.Column("causation_id", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("position", name=op.f("pk_runtime_events")),
        sa.UniqueConstraint("event_id", name="uq_runtime_events_event_id"),
    )
    op.create_index(op.f("ix_runtime_events_event_type"), "runtime_events", ["event_type"])
    op.create_index(op.f("ix_runtime_events_aggregate_id"), "runtime_events", ["aggregate_id"])
    op.create_index(op.f("ix_runtime_events_job_id"), "runtime_events", ["job_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_runtime_events_job_id"), table_name="runtime_events")
    op.drop_index(op.f("ix_runtime_events_aggregate_id"), table_name="runtime_events")
    op.drop_index(op.f("ix_runtime_events_event_type"), table_name="runtime_events")
    op.drop_table("runtime_events")
