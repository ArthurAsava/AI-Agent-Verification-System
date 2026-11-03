
"""add agent onboarding table

Revision ID: e66494f32ff5
Revises: ee19ec17be65
Create Date: 2026-11-03 10:39:52.635324
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revision identifiers
revision: str = "e66494f32ff5"
down_revision: Union[str, Sequence[str], None] = "ee19ec17be65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent onboarding table and configure RLS."""

    # 1. Create the onboarding table
    op.create_table(
        "agent_onboarding",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "county",
            sa.String(length=100),
            nullable=True,
        ),

        sa.Column(
            "city",
            sa.String(length=100),
            nullable=True,
        ),

        sa.Column(
            "business_name",
            sa.String(length=150),
            nullable=True,
        ),

        sa.Column(
            "experience_level",
            sa.String(length=30),
            nullable=True,
        ),

        sa.Column(
            "preferred_sales_category",
            sa.String(length=100),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint("agent_id"),
    )

    # 2. Create index for faster agent lookups
    op.create_index(
        "ix_agent_onboarding_agent_id",
        "agent_onboarding",
        ["agent_id"],
        unique=True,
    )

    # 3. Enable Row-Level Security
    op.execute("""
        ALTER TABLE public.agent_onboarding
        ENABLE ROW LEVEL SECURITY
    """)

    # 4. Allow authenticated agents to read
    # only their own onboarding records
    op.execute("""
        CREATE POLICY onboarding_select_own
        ON public.agent_onboarding
        FOR SELECT
        TO authenticated
        USING (
            EXISTS (
                SELECT 1
                FROM public.agents a
                WHERE a.id = agent_id
                  AND a.user_id = (SELECT auth.uid())
            )
        )
    """)

    # 5. Grant read-only access
    op.execute("""
        GRANT SELECT
        ON public.agent_onboarding
        TO authenticated
    """)


def downgrade() -> None:
    """Remove agent onboarding table safely."""

    # 1. Remove the RLS policy
    op.execute("""
        DROP POLICY IF EXISTS onboarding_select_own
        ON public.agent_onboarding
    """)

    # 2. Remove the index
    op.drop_index(
        "ix_agent_onboarding_agent_id",
        table_name="agent_onboarding",
    )

    # 3. Remove the onboarding table
    op.drop_table("agent_onboarding")
