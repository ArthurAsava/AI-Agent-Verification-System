"""Repair verification workflow schema and row-level security.

Revision ID: c9447ad1e6f0
Revises: 63819b6d4435
Create Date: 2026-11-12 10:00:00.000000
"""

from alembic import op


revision = "c9447ad1e6f0"
down_revision = "63819b6d4435"
branch_labels = None
depends_on = None


APPLICATION_TABLES = (
    "agents",
    "agent_onboarding",
    "kyc_documents",
    "verification_checks",
    "verification_cases",
    "verification_reviewers",
    "fraud_assessments",
    "audit_logs",
)


def upgrade() -> None:
    """Create omitted workflow tables and enforce the intended RLS boundary."""

    # Three earlier revisions were generated without operations. The IF NOT
    # EXISTS clauses make this corrective migration safe for environments
    # where an administrator created the omitted tables manually.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.verification_cases (
            id UUID NOT NULL,
            agent_id UUID NOT NULL REFERENCES public.agents(id),
            document_id UUID NOT NULL REFERENCES public.kyc_documents(id),
            processing_key VARCHAR(255) NOT NULL,
            status VARCHAR(40) NOT NULL,
            recommendation VARCHAR(40),
            risk_score INTEGER,
            risk_level VARCHAR(20),
            scoring_version VARCHAR(50),
            reviewer_user_id UUID,
            decision_reason TEXT,
            version INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            reviewed_at TIMESTAMPTZ,
            CONSTRAINT pk_verification_cases PRIMARY KEY (id),
            CONSTRAINT uq_verification_case_processing_key
                UNIQUE (processing_key)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_verification_cases_agent_id
        ON public.verification_cases (agent_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_verification_cases_document_id
        ON public.verification_cases (document_id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.verification_reviewers (
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            is_active BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT pk_verification_reviewers PRIMARY KEY (user_id)
        )
        """
    )

    for table in APPLICATION_TABLES:
        op.execute(
            f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"
        )
        op.execute(
            f"REVOKE ALL ON TABLE public.{table} FROM anon, authenticated"
        )

    # Recreate the agent-facing read policies. Earlier migrations attempted
    # this but did not actually enable RLS because their upgrade function was
    # overwritten by a later empty definition.
    for table, policy in (
        ("agents", "agents_select_own"),
        ("agent_onboarding", "onboarding_select_own"),
        ("kyc_documents", "documents_select_own"),
        ("verification_checks", "checks_select_own"),
        ("verification_cases", "verification_cases_select_own"),
    ):
        op.execute(
            f"DROP POLICY IF EXISTS {policy} ON public.{table}"
        )

    op.execute(
        """
        CREATE POLICY agents_select_own
        ON public.agents
        FOR SELECT TO authenticated
        USING ((SELECT auth.uid()) = user_id)
        """
    )
    op.execute(
        """
        CREATE POLICY onboarding_select_own
        ON public.agent_onboarding
        FOR SELECT TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM public.agents a
                WHERE a.id = agent_id
                  AND a.user_id = (SELECT auth.uid())
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY documents_select_own
        ON public.kyc_documents
        FOR SELECT TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM public.agents a
                WHERE a.id = agent_id
                  AND a.user_id = (SELECT auth.uid())
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY checks_select_own
        ON public.verification_checks
        FOR SELECT TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM public.agents a
                WHERE a.id = agent_id
                  AND a.user_id = (SELECT auth.uid())
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY verification_cases_select_own
        ON public.verification_cases
        FOR SELECT TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM public.agents a
                WHERE a.id = agent_id
                  AND a.user_id = (SELECT auth.uid())
            )
        )
        """
    )

    op.execute(
        """
        GRANT SELECT ON TABLE
            public.agents,
            public.agent_onboarding,
            public.kyc_documents,
            public.verification_checks,
            public.verification_cases
        TO authenticated
        """
    )


def downgrade() -> None:
    """Security repair is intentionally forward-only."""

    raise RuntimeError(
        "Downgrading this security repair can expose protected data."
    )
