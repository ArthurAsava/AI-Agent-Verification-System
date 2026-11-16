
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import Agent, AgentStatus, KYCDocument
from app.models.verification_case import VerificationCase, utc_now

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
from app.services.verification.fraud_signal_service import (
    assessment_key_for,
    collect_trusted_fraud_signal_evidence,
)
from app.services.verification.risk_contract_adapter import (
    to_risk_assessment_contract,
)
from app.services.verification.risk_engine import assess_risk
from app.services.verification.recommendation import (
    build_recommendation,
)
from app.services.profile_avatar_service import (
    avatar_variant_from_document_sex,
)
from app.services.verification.decision_contracts import CaseStatus
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
    case_id: UUID | None = None


def _run_verification_sync(
    *,
    user_id: UUID,
    document_id: UUID,
    document_bytes: bytes,
    expected_storage_path: str,
    expected_storage_bucket: str,
    expected_checksum: str,
    case_id: UUID | None = None,
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

            base_features = extract_risk_features_from_analysis(
                workflow.pipeline_result
            )

            evidence = collect_trusted_fraud_signal_evidence(
                db=db,
                agent_id=agent.id,
                document_id=document.id,
                current_check_id=workflow.check_id,
            )
            features = evidence.apply_to(base_features)

            risk = assess_risk(features)

            contract = to_risk_assessment_contract(
                agent_id=agent.id,
                result=risk,
                indicator_evidence=evidence.indicator_evidence(),
            )

            assessment = save_risk_assessment(
                db=db,
                result=contract,
                actor_user_id=user_id,
                commit=False,
                verification_case_id=case_id,
                assessment_key=assessment_key_for(
                    agent_id=agent.id,
                    document_id=document.id,
                    case_id=case_id,
                    features=features,
                    scoring_version=risk.risk.scoring_version,
                ),
            )

            recommendation = build_recommendation(
                risk,
                document_analysis_passed=(
                    workflow.pipeline_result.analysis.outcome
                    == VerificationOutcome.PASS
                ),
            )

            if case_id is not None:
                case = db.execute(
                    select(VerificationCase)
                    .where(
                        VerificationCase.id == case_id,
                        VerificationCase.agent_id == agent.id,
                    )
                    .with_for_update()
                ).scalar_one_or_none()

                if case is None:
                    raise VerificationIntegrityError(
                        "Verification case not found"
                    )

                if case.status != CaseStatus.ANALYZING.value:
                    raise VerificationIntegrityError(
                        "Verification case is not analyzing"
                    )

                case.status = CaseStatus.AWAITING_REVIEW.value
                case.recommendation = recommendation.recommendation.value
                case.risk_score = risk.risk.score
                case.risk_level = risk.risk.level
                case.scoring_version = risk.risk.scoring_version
                case.avatar_variant = avatar_variant_from_document_sex(
                    workflow.pipeline_result.document_sex
                )
                case.updated_at = utc_now()
                case.version += 1

                # Automated analysis can only place an agent under review.
                # It cannot grant access.
                agent.status = AgentStatus.UNDER_REVIEW

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
                case_id=case_id,
            )

        except Exception:
            db.rollback()
            raise


async def run_complete_verification(
    *,
    user_id: UUID,
    document_id: UUID,
    storage: SupabaseStorageService,
    case_id: UUID | None = None,
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
        case_id=case_id,
    )
