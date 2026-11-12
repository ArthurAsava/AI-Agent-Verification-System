
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import Agent, KYCDocument

from app.services.kyc_retrieval_service import (
    download_agent_document,
)
from app.services.storage_service import SupabaseStorageService

from app.services.verification.contracts import (
    VerificationOutcome,
)
from app.services.verification.workflow import (
    run_document_verification,
)
from app.services.verification.risk_feature_adapter import (
    extract_risk_features_from_analysis,
)
from app.services.verification.risk_contract_adapter import (
    to_risk_assessment_contract,
)
from app.services.verification.risk_engine import assess_risk
from app.services.verification.recommendation import (
    build_recommendation,
)
from app.services.verification.persistence import (
    VerificationIntegrityError,
    save_risk_assessment,
)


@dataclass(frozen=True)
class CompleteVerificationResult:
    agent_id: UUID
    document_id: UUID
    check_id: UUID
    assessment_id: UUID
    risk_score: int
    risk_level: str
    recommendation: str
    indicator_codes: tuple[str, ...]


def _run_verification_sync(
    *,
    user_id: UUID,
    document_id: UUID,
    document_bytes: bytes,
    expected_storage_path: str,
    expected_storage_bucket: str,
    expected_checksum: str,
) -> CompleteVerificationResult:

    with SessionLocal() as db:
        try:
            agent = db.execute(
                select(Agent).where(
                    Agent.user_id == user_id
                )
            ).scalar_one_or_none()

            if agent is None:
                raise VerificationIntegrityError(
                    "Agent not found"
                )

            document = db.execute(
                select(KYCDocument).where(
                    KYCDocument.id == document_id,
                    KYCDocument.agent_id == agent.id,
                )
            ).scalar_one_or_none()

            if document is None:
                raise VerificationIntegrityError(
                    "Document not found"
                )

            if (
                document.storage_path != expected_storage_path
                or document.storage_bucket != expected_storage_bucket
                or document.sha256_checksum != expected_checksum
            ):
                raise VerificationIntegrityError(
                    "Document reference changed"
                )

            workflow = run_document_verification(
                db=db,
                agent_id=agent.id,
                document_id=document.id,
                document_bytes=document_bytes,
                actor_user_id=user_id,
                commit=False,
            )

            features = extract_risk_features_from_analysis(
                workflow.pipeline_result
            )

            risk = assess_risk(features)

            contract = to_risk_assessment_contract(
                agent_id=agent.id,
                result=risk,
            )

            assessment = save_risk_assessment(
                db=db,
                result=contract,
                actor_user_id=user_id,
                commit=False,
            )

            recommendation = build_recommendation(
                risk,
                document_analysis_passed=(
                    workflow.pipeline_result.analysis.outcome
                    == VerificationOutcome.PASS
                ),
            )

            db.commit()

            return CompleteVerificationResult(
                agent_id=agent.id,
                document_id=document.id,
                check_id=workflow.check_id,
                assessment_id=assessment.id,
                risk_score=risk.risk.score,
                risk_level=risk.risk.level,
                recommendation=(
                    recommendation.recommendation.value
                ),
                indicator_codes=tuple(
                    indicator.code
                    for indicator in risk.indicators
                ),
            )

        except Exception:
            db.rollback()
            raise


async def run_complete_verification(
    *,
    user_id: UUID,
    document_id: UUID,
    storage: SupabaseStorageService,
) -> CompleteVerificationResult:

    document, content = await download_agent_document(
        user_id=user_id,
        document_id=document_id,
        storage=storage,
    )

    # Retrieve the expected checksum from the same
    # authorized document record. The current
    # DocumentInfo does not expose it, so the
    # retrieval service must be extended to do so.
    if not document.sha256_checksum:
        raise VerificationIntegrityError(
            "Authorized document checksum unavailable"
        )

    return await run_in_threadpool(
        _run_verification_sync,
        user_id=user_id,
        document_id=document_id,
        document_bytes=content,
        expected_storage_path=document.storage_path,
        expected_storage_bucket=document.storage_bucket,
        expected_checksum=document.sha256_checksum,
    )
