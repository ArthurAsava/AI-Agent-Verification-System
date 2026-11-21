from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models.entities import Agent, AgentStatus, KYCDocument
from app.models.verification_case import VerificationCase, utc_now
from app.services.kyc_upload_service import (
    DOCUMENT_REQUIREMENTS_MESSAGE,
    has_complete_document_set,
)
from app.services.storage_service import SupabaseStorageService
from app.services.verification.decision_contracts import CaseStatus
from app.services.verification.persistence import VerificationIntegrityError
from app.services.verification.verification_orchestrator import (
    run_complete_verification,
)


logger = logging.getLogger(__name__)


ANALYZABLE_DOCUMENT_TYPES = frozenset({
    "national_id_front",
    "passport",
})


class VerificationDocumentNotFoundError(ValueError):
    """The authenticated agent does not own the requested document."""


@dataclass(frozen=True)
class VerificationSubmissionResult:
    case_id: UUID
    status: str
    started: bool


def _processing_key(
    *,
    agent_id: UUID,
    document_id: UUID,
    checksum: str,
) -> str:
    return (
        "document-verification-v1:"
        f"{agent_id}:{document_id}:{checksum}"
    )


def _start_submission_sync(
    *,
    user_id: UUID,
    document_id: UUID,
) -> VerificationSubmissionResult:
    """Create or reuse a server-owned, idempotent verification case."""

    with SessionLocal() as db:
        agent = db.execute(
            select(Agent).where(Agent.user_id == user_id)
        ).scalar_one_or_none()

        if agent is None:
            raise VerificationDocumentNotFoundError(
                "Agent profile not found."
            )

        document = db.execute(
            select(KYCDocument).where(
                KYCDocument.id == document_id,
                KYCDocument.agent_id == agent.id,
            )
        ).scalar_one_or_none()

        if document is None:
            raise VerificationDocumentNotFoundError(
                "Document not found."
            )

        if document.document_type not in ANALYZABLE_DOCUMENT_TYPES:
            raise VerificationIntegrityError(
                "This document type cannot be used for identity analysis."
            )

        document_types = db.execute(
            select(KYCDocument.document_type).where(
                KYCDocument.agent_id == agent.id
            )
        ).scalars().all()
        if not has_complete_document_set(document_types):
            raise VerificationIntegrityError(
                DOCUMENT_REQUIREMENTS_MESSAGE
            )

        if not document.sha256_checksum:
            raise VerificationIntegrityError(
                "Document integrity metadata is unavailable."
            )

        processing_key = _processing_key(
            agent_id=agent.id,
            document_id=document.id,
            checksum=document.sha256_checksum,
        )

        case = db.execute(
            select(VerificationCase).where(
                VerificationCase.processing_key == processing_key
            )
        ).scalar_one_or_none()

        if case is not None:
            if case.status in {
                CaseStatus.PENDING.value,
                CaseStatus.ANALYSIS_FAILED.value,
            }:
                case.status = CaseStatus.ANALYZING.value
                case.updated_at = utc_now()
                case.version += 1
                agent.status = AgentStatus.UNDER_REVIEW
                db.commit()
                return VerificationSubmissionResult(
                    case_id=case.id,
                    status=case.status,
                    started=True,
                )

            return VerificationSubmissionResult(
                case_id=case.id,
                status=case.status,
                started=False,
            )

        case = VerificationCase(
            agent_id=agent.id,
            document_id=document.id,
            processing_key=processing_key,
            status=CaseStatus.ANALYZING.value,
        )
        db.add(case)
        agent.status = AgentStatus.UNDER_REVIEW

        try:
            db.commit()
        except IntegrityError:
            # A concurrent request may have created the same idempotent case.
            db.rollback()
            existing = db.execute(
                select(VerificationCase).where(
                    VerificationCase.processing_key == processing_key
                )
            ).scalar_one_or_none()

            if existing is None:
                raise

            return VerificationSubmissionResult(
                case_id=existing.id,
                status=existing.status,
                started=False,
            )

        db.refresh(case)

        return VerificationSubmissionResult(
            case_id=case.id,
            status=case.status,
            started=True,
        )


def _get_case_status_sync(case_id: UUID) -> str:
    with SessionLocal() as db:
        case = db.execute(
            select(VerificationCase).where(
                VerificationCase.id == case_id
            )
        ).scalar_one_or_none()

        if case is None:
            raise VerificationIntegrityError(
                "Verification case not found."
            )

        return case.status


def _mark_analysis_failed_sync(case_id: UUID) -> None:
    """Record a failed analysis without exposing its internals to the agent."""

    with SessionLocal() as db:
        case = db.execute(
            select(VerificationCase)
            .where(VerificationCase.id == case_id)
            .with_for_update()
        ).scalar_one_or_none()

        if case is None or case.status != CaseStatus.ANALYZING.value:
            return

        agent = db.execute(
            select(Agent).where(Agent.id == case.agent_id)
        ).scalar_one_or_none()

        case.status = CaseStatus.ANALYSIS_FAILED.value
        case.updated_at = utc_now()
        case.version += 1

        if agent is not None:
            agent.status = AgentStatus.PENDING

        db.commit()


async def submit_document_for_verification(
    *,
    user_id: UUID,
    document_id: UUID,
    storage: SupabaseStorageService,
) -> VerificationSubmissionResult:
    """Run one agent-owned document through the human-review workflow."""

    submission = await run_in_threadpool(
        _start_submission_sync,
        user_id=user_id,
        document_id=document_id,
    )

    if not submission.started:
        return submission

    try:
        await run_complete_verification(
            user_id=user_id,
            document_id=document_id,
            storage=storage,
            case_id=submission.case_id,
        )
    except Exception:
        try:
            await run_in_threadpool(
                _mark_analysis_failed_sync,
                submission.case_id,
            )
        except Exception:
            logger.exception(
                "Could not record verification analysis failure."
            )
        raise

    return VerificationSubmissionResult(
        case_id=submission.case_id,
        status=await run_in_threadpool(
            _get_case_status_sync,
            submission.case_id,
        ),
        started=True,
    )
