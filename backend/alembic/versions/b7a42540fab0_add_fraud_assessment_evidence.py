"""Add data-minimized, reviewable fraud assessment evidence.

Revision ID: b7a42540fab0
Revises: c9447ad1e6f0
Create Date: 2026-11-15 22:41:40.608301

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b7a42540fab0"
down_revision = "c9447ad1e6f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Persist explainable fraud signals without retaining identity data."""

    # Existing assessments receive an opaque stable key before it becomes
    # required. The value is derived only from the assessment UUID, not from
    # an agent, document, biometric, or provider payload.
    op.execute(
        """
        ALTER TABLE public.fraud_assessments
            ADD COLUMN IF NOT EXISTS verification_case_id UUID
                REFERENCES public.verification_cases(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS assessment_key VARCHAR(64),
            ADD COLUMN IF NOT EXISTS signals JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS requires_review BOOLEAN NOT NULL DEFAULT true
        """
    )
    op.execute(
        """
        UPDATE public.fraud_assessments
        SET assessment_key = md5('legacy-fraud-assessment:' || id::text)
        WHERE assessment_key IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.fraud_assessments
            ALTER COLUMN assessment_key SET NOT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_fraud_assessments_assessment_key'
            ) THEN
                ALTER TABLE public.fraud_assessments
                    ADD CONSTRAINT uq_fraud_assessments_assessment_key
                    UNIQUE (assessment_key);
            END IF;
        END $$;
        """
    )

    # Both lookups are used only by the trusted backend fraud-signal service.
    # No table exposure, grants, RLS setting, or policy changes are made here.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_fraud_assessments_verification_case_id
        ON public.fraud_assessments (verification_case_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_kyc_documents_sha256_checksum
        ON public.kyc_documents (sha256_checksum)
        WHERE sha256_checksum IS NOT NULL
        """
    )


def downgrade() -> None:
    """This evidence migration is intentionally forward-only."""
    raise RuntimeError(
        "Fraud assessment evidence is retained for review and auditability."
    )
