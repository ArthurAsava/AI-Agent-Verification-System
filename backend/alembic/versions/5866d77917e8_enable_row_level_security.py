"""enable row level security

Revision ID: 5866d77917e8
Revises: e48a58879130
Create Date: 2026-10-27 11:08:16.412592

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5866d77917e8'
down_revision: Union[str, Sequence[str], None] = 'e48a58879130'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op


TABLES = (
    "agents",
    "kyc_documents",
    "verification_checks",
    "fraud_assessments",
    "audit_logs",
)


def upgrade():
    for table in TABLES:
        op.execute(
            f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"
        )

    # Authenticated agents can view their own profile.
    op.execute("""
        CREATE POLICY agents_select_own
        ON public.agents
        FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = user_id)
    """)

    # Agents can view their own document metadata.
    # Storage objects require separate policies.
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

    # Agents can see their own verification statuses.
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

    # No client-side access policies for fraud_assessments
    # or audit_logs. These remain restricted to trusted
    # backend/database roles.

    # Restrict direct API-role privileges.
    for table in TABLES:
        op.execute(
            f"REVOKE ALL ON TABLE public.{table} "
            "FROM anon, authenticated"
        )

    # Read-only access to selected tables, subject to RLS.
    for table in (
        "agents",
        "kyc_documents",
        "verification_checks",
    ):
        op.execute(
            f"GRANT SELECT ON TABLE public.{table} TO authenticated"
        )


def downgrade():
    for table, policy in (
        ("agents", "agents_select_own"),
        ("kyc_documents", "documents_select_own"),
        ("verification_checks", "checks_select_own"),
    ):
        op.execute(
            f"DROP POLICY IF EXISTS {policy} ON public.{table}"
        )

    for table in TABLES:
        op.execute(
            f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY"
        )

def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
