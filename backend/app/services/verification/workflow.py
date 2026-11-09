
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Agent, KYCDocument

from app.services.verification.identity_matcher import (
    AgentIdentityReference,
)
from app.services.verification.pipeline import (
    VerificationPipelineResult,
    analyze_kyc_document,
)
from app.services.verification.persistence import (
    VerificationIntegrityError,
    save_document_analysis,
)
from app.services.verification.document_integrity import (
    verify_document_integrity,
)

@dataclass(frozen=True)
class VerificationWorkflowResult:
    check_id: UUID
    pipeline_result: VerificationPipelineResult


def run_document_verification(
    *,
    db: Session,
    agent_id: UUID,
    document_id: UUID,
    document_bytes: bytes,
    actor_user_id: UUID | None = None,
) -> VerificationWorkflowResult:
    """
    Verify a document belonging to an agent.

    SECURITY:
    Call only from a trusted backend job or an
    authorized application service.

    The caller must have already retrieved the
    document bytes from the private storage object
    identified by the checked KYCDocument record.
    """

    agent = db.execute(
        select(Agent).where(
            Agent.id == agent_id
        )
    ).scalar_one_or_none()

    if agent is None:
        raise VerificationIntegrityError(
            "Agent does not exist."
        )


    document = db.execute(
        select(KYCDocument).where(
            KYCDocument.id == document_id,
            KYCDocument.agent_id == agent_id,
        )
    ).scalar_one_or_none()

    if document is None:
        raise VerificationIntegrityError(
            "Document does not belong to the agent."
        )

    # Verify document integrity before running OCR.
    verify_document_integrity(
        content=document_bytes,
        expected_checksum=document.sha256_checksum,
    )

    # Construct the registered agent identity reference.
    reference = AgentIdentityReference(
        first_name=agent.first_name,
        last_name=agent.last_name,
    )

    # Run the verification pipeline.
    pipeline_result = analyze_kyc_document(
        document_id=document.id,
        document_type=document.document_type,
        content=document_bytes,
        mime_type=document.mime_type,
        agent_reference=reference,
    )

    # Save the verification result.
    check = save_document_analysis(
        db=db,
        agent_id=agent_id,
        result=pipeline_result.analysis,
        actor_user_id=actor_user_id,
    )

    return VerificationWorkflowResult(
        check_id=check.id,
        pipeline_result=pipeline_result,
    )

