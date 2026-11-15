"""Add a server-enforced administrator capability for verification staff.

Revision ID: ff2e99f8c987
Revises: b7a42540fab0
Create Date: 2026-11-15 23:08:47.717821

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ff2e99f8c987"
down_revision = "b7a42540fab0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep administrator capability separate from reviewer activity."""

    # No table exposure, grant, RLS, or RLS-policy settings are changed here.
    # The FastAPI authorization dependency remains the enforcement point.
    op.execute(
        """
        ALTER TABLE public.verification_reviewers
            ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT false
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_verification_reviewers_active_admin
        ON public.verification_reviewers (user_id)
        WHERE is_active IS TRUE AND is_admin IS TRUE
        """
    )


def downgrade() -> None:
    """Administrator authorization records are intentionally forward-only."""
    raise RuntimeError(
        "Administrator capability changes must be superseded by a new migration."
    )
