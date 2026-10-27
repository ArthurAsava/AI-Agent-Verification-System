"""add missing agent rls policies

Revision ID: ee19ec17be65
Revises: 5866d77917e8
Create Date: 2026-10-27 11:26:32.889059

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee19ec17be65'
down_revision: Union[str, Sequence[str], None] = '5866d77917e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE POLICY agents_select_own
        ON public.agents
        FOR SELECT
        TO authenticated
        USING (
            (SELECT auth.uid()) = user_id
        )
    """)

    op.execute("""
        CREATE POLICY documents_select_own
        ON public.kyc_documents
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

    op.execute("""
        CREATE POLICY checks_select_own
        ON public.verification_checks
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

    # Ensure authenticated users have the table privileges
    # required to use these read-only policies.
    op.execute("""
        GRANT SELECT ON TABLE
            public.agents,
            public.kyc_documents,
            public.verification_checks
        TO authenticated
    """)


def downgrade() -> None:
    op.execute("""
        DROP POLICY IF EXISTS checks_select_own
        ON public.verification_checks
    """)

    op.execute("""
        DROP POLICY IF EXISTS documents_select_own
        ON public.kyc_documents
    """)

    op.execute("""
        DROP POLICY IF EXISTS agents_select_own
        ON public.agents
    """)
