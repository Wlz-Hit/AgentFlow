"""Alembic revision template."""

revision = $REVISION
down_revision = $DOWN_REVISION
branch_labels = $BRANCH_LABELS
depends_on = $DEPENDS_ON

from alembic import op  # noqa: E402
import sqlalchemy as sa  # noqa: E402


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
