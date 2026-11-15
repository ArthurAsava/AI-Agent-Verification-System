
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db

from app.models.entities import Agent
from app.models.verification_case import VerificationCase

from app.schemas.verification_api import (
    AgentVerificationResponse,
    ReviewQueueResponse,
    ReviewerCaseDetail,
    VerificationAnalysisResponse,
    VerificationCaseSummary,
    VerificationDecisionRequest,
    VerificationDecisionResponse,
)

from app.services.verification.reviewer_service import (
    record_verification_decision,
    ReviewerAuthorizationError,
    VerificationCaseNotFoundError,
    VerificationDecisionConflictError,
    VerificationDecisionValidationError,
    VerificationDecisionPersistenceError,
)
from app.core.reviewer_auth import require_reviewer
from app.services.kyc_retrieval_service import (
    DocumentNotFoundError,
    DocumentRetrievalError,
)
from app.services.storage_service import (
    SupabaseStorageService,
    get_storage_service,
)
from app.services.verification.document_integrity import (
    DocumentIntegrityError,
)
from app.services.verification.document_processor import (
    DocumentProcessingError,
)
from app.services.verification.identity_extractor import (
    IdentityExtractionError,
)
from app.services.verification.ocr_service import OCRProcessingError
from app.services.verification.persistence import (
    VerificationIntegrityError,
    VerificationPersistenceError,
)
from app.services.verification.submission_service import (
    VerificationDocumentNotFoundError,
    submit_document_for_verification,
)

router = APIRouter(
    prefix="/verification",
    tags=["Verification"],
)


# Authentication helpers

def _authenticated_user_id(user: Any) -> UUID:
    """
    Extract the authenticated Supabase user ID.

    The value must come from the trusted authentication
    dependency, not from a request body or query parameter.
    """

    if isinstance(user, UUID):
        return user

    if isinstance(user, dict):
        raw_id = user.get("id") or user.get("user_id")
    else:
        raw_id = getattr(user, "id", None)

        if raw_id is None:
            raw_id = getattr(user, "user_id", None)

    if raw_id is None:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user ID is unavailable.",
        )

    try:
        return UUID(str(raw_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid authenticated user ID.",
        )


# Agent verification status


@router.post(
    "/documents/{document_id}/submit",
    response_model=VerificationAnalysisResponse,
)
async def submit_verification_document(
    document_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    storage: SupabaseStorageService = Depends(get_storage_service),
):
    """Submit one owned identity document for human-reviewed verification."""

    try:
        result = await submit_document_for_verification(
            user_id=user.id,
            document_id=document_id,
            storage=storage,
        )
    except (
        VerificationDocumentNotFoundError,
        DocumentNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=404,
            detail="KYC document not found.",
        ) from exc
    except DocumentRetrievalError as exc:
        raise HTTPException(
            status_code=503,
            detail="Document retrieval is temporarily unavailable.",
        ) from exc
    except (
        VerificationIntegrityError,
        DocumentIntegrityError,
        DocumentProcessingError,
        OCRProcessingError,
        IdentityExtractionError,
    ) as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "This document could not be analyzed. "
                "Please upload a clear supported identity document."
            ),
        ) from exc
    except VerificationPersistenceError as exc:
        raise HTTPException(
            status_code=500,
            detail="Verification results could not be saved.",
        ) from exc

    if result.status == "awaiting_review":
        message = (
            "Document analysis completed. Your case is awaiting "
            "a human review."
        )
    elif result.status == "analyzing":
        message = "Your document is already being analyzed."
    else:
        message = "Your existing verification case was reused."

    return VerificationAnalysisResponse(
        case_id=result.case_id,
        status=result.status,
        message=message,
    )

@router.get(
    "/me",
    response_model=AgentVerificationResponse,
)
def get_my_verification(
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_user),
):
    user_id = _authenticated_user_id(user)

    agent = db.execute(
        select(Agent).where(
            Agent.user_id == user_id
        )
    ).scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent profile not found.",
        )

    cases = db.execute(
        select(VerificationCase)
        .where(
            VerificationCase.agent_id == agent.id
        )
        .order_by(
            VerificationCase.created_at.desc()
        )
    ).scalars().all()

    return AgentVerificationResponse(
        cases=[
            VerificationCaseSummary.model_validate(case)
            for case in cases
        ]
    )


# ---------------------------------------------------------
# Reviewer queue
# ---------------------------------------------------------

@router.get(
    "/review-queue",
    response_model=ReviewQueueResponse,
)
def get_review_queue(
    db: Session = Depends(get_db),
    reviewer_id: UUID = Depends(require_reviewer),
):
    cases = db.execute(
        select(VerificationCase)
        .where(
            VerificationCase.status == "awaiting_review"
        )
        .order_by(
            VerificationCase.created_at.asc()
        )
    ).scalars().all()

    return ReviewQueueResponse(
        cases=[
            ReviewerCaseDetail.model_validate(case)
            for case in cases
        ]
    )


# ---------------------------------------------------------
# Reviewer case details
# ---------------------------------------------------------

@router.get(
    "/cases/{case_id}",
    response_model=ReviewerCaseDetail,
)
def get_verification_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    reviewer_id: UUID = Depends(require_reviewer),
):
    case = db.execute(
        select(VerificationCase).where(
            VerificationCase.id == case_id
        )
    ).scalar_one_or_none()

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Verification case not found.",
        )

    return ReviewerCaseDetail.model_validate(case)


# ---------------------------------------------------------
# Reviewer decision
# ---------------------------------------------------------

@router.post(
    "/cases/{case_id}/decision",
    response_model=VerificationDecisionResponse,
)
def decide_verification_case(
    case_id: UUID,
    payload: VerificationDecisionRequest,
    db: Session = Depends(get_db),
    reviewer_id: UUID = Depends(require_reviewer),
):
    try:
        result = record_verification_decision(
            db=db,
            case_id=case_id,
            reviewer_user_id=reviewer_id,
            action=payload.action,
            reason=payload.reason,
            expected_version=payload.expected_version,
            reviewer_authorized=True,
        )

        return VerificationDecisionResponse(
            case_id=result.case_id,
            previous_status=result.previous_status,
            new_status=result.new_status,
            version=result.version,
            reviewed_at=result.reviewed_at,
        )

    except VerificationCaseNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Verification case not found.",
        )

    except ReviewerAuthorizationError:
        raise HTTPException(
            status_code=403,
            detail="Reviewer permission denied.",
        )

    except VerificationDecisionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    except VerificationDecisionValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    except VerificationDecisionPersistenceError:
        raise HTTPException(
            status_code=500,
            detail="Could not save verification decision.",
        )
