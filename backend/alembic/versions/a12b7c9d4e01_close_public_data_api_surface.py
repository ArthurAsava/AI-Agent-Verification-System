"""Close the public Data API surface behind the FastAPI boundary.

Revision ID: a12b7c9d4e01
Revises: ff2e99f8c987
Create Date: 2026-11-16 12:00:00.000000
"""

from alembic import op


revision = "a12b7c9d4e01"
down_revision = "ff2e99f8c987"
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

SERVER_ONLY_TABLES = (
    "verification_reviewers",
    "fraud_assessments",
    "audit_logs",
    "alembic_version",
)


def upgrade() -> None:
    """Keep browser clients out of public tables and migration metadata.

    The frontend uses Supabase Auth for sessions and calls the FastAPI API for
    every application-data operation.  It has no supported direct PostgREST
    table access, so grants to ``anon`` and ``authenticated`` only enlarge the
    attack surface.  RLS remains enabled as defence in depth for future role
    changes, while the trusted backend database role retains its server-only
    access.
    """

    for table in (*APPLICATION_TABLES, "alembic_version"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"REVOKE ALL ON TABLE public.{table} "
            "FROM PUBLIC, anon, authenticated"
        )

    # These tables intentionally have no browser-visible records. A
    # restrictive deny policy makes that explicit and remains protective if a
    # client role is accidentally granted table privileges in the future.
    for table in SERVER_ONLY_TABLES:
        policy = f"{table}_block_direct_api_access"
        op.execute(
            f"DROP POLICY IF EXISTS {policy} ON public.{table}"
        )
        op.execute(
            f"CREATE POLICY {policy} ON public.{table} "
            "AS RESTRICTIVE FOR ALL TO PUBLIC "
            "USING (false) WITH CHECK (false)"
        )


def downgrade() -> None:
    """Security hardening is intentionally forward-only."""

    raise RuntimeError(
        "Restoring direct browser table access requires an explicit migration."
    )
