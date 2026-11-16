"""Persist the server-controlled visual variant for verified identities.

Revision ID: 7ca3e0b7ffe6
Revises: a12b7c9d4e01
Create Date: 2026-11-16 15:36:17.759030
"""

from alembic import op


revision = "7ca3e0b7ffe6"
down_revision = "a12b7c9d4e01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add one constrained display value without changing table exposure."""
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE public.avatar_variant AS ENUM ('male', 'female');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    for table in ("agents", "verification_cases"):
        op.execute(
            f"""
            ALTER TABLE public.{table}
            ADD COLUMN IF NOT EXISTS avatar_variant public.avatar_variant
            """
        )


def downgrade() -> None:
    """Remove the presentation-only fields on an explicit rollback."""
    op.execute(
        "ALTER TABLE public.verification_cases DROP COLUMN IF EXISTS avatar_variant"
    )
    op.execute(
        "ALTER TABLE public.agents DROP COLUMN IF EXISTS avatar_variant"
    )
    op.execute("DROP TYPE IF EXISTS public.avatar_variant")
