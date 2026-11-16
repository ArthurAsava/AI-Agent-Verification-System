"""Remove the duplicate onboarding agent lookup index.

Revision ID: d8e4f9a1c2b7
Revises: 7ca3e0b7ffe6
Create Date: 2026-11-16 23:20:00.000000
"""

from alembic import op


revision = "d8e4f9a1c2b7"
down_revision = "7ca3e0b7ffe6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Retain the unique constraint's index and remove its duplicate."""
    op.drop_index(
        "ix_agent_onboarding_agent_id",
        table_name="agent_onboarding",
    )


def downgrade() -> None:
    """Restore the historical duplicate index on an explicit rollback."""
    op.create_index(
        "ix_agent_onboarding_agent_id",
        "agent_onboarding",
        ["agent_id"],
        unique=True,
    )
