"""Persistence hardening: RunAttempt.updated_at and QueueItem job consistency.

Revision ID: 0002_persistence_hardening
Revises: 0001_domain_tables
Create Date: 2026-09-22

Backfill note: interrupted RunAttempts from TASK-003 did not store the exact
interruption timestamp. Non-terminal rows are backfilled from started_at when
present, otherwise created_at. Terminal rows use finished_at.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_persistence_hardening"
down_revision: str | None = "0001_domain_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run_attempts") as batch:
        batch.add_column(sa.Column("updated_at", sa.String(length=64), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE run_attempts
            SET updated_at = CASE
                WHEN finished_at IS NOT NULL THEN finished_at
                WHEN started_at IS NOT NULL THEN started_at
                ELSE created_at
            END
            """
        )
    )

    with op.batch_alter_table("run_attempts") as batch:
        batch.alter_column("updated_at", existing_type=sa.String(length=64), nullable=False)

    with op.batch_alter_table("workflow_steps") as batch:
        batch.create_unique_constraint("uq_workflow_steps_id_job", ["id", "job_id"])

    with op.batch_alter_table(
        "queue_items",
        recreate="always",
    ) as batch:
        batch.drop_constraint(
            op.f("fk_queue_items_workflow_step_id_workflow_steps"),
            type_="foreignkey",
        )
        batch.create_foreign_key(
            "fk_queue_items_workflow_step_job",
            "workflow_steps",
            ["workflow_step_id", "job_id"],
            ["id", "job_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("queue_items", recreate="always") as batch:
        batch.drop_constraint("fk_queue_items_workflow_step_job", type_="foreignkey")
        batch.create_foreign_key(
            op.f("fk_queue_items_workflow_step_id_workflow_steps"),
            "workflow_steps",
            ["workflow_step_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("workflow_steps") as batch:
        batch.drop_constraint("uq_workflow_steps_id_job", type_="unique")

    with op.batch_alter_table("run_attempts") as batch:
        batch.drop_column("updated_at")
