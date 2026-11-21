
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db

from app.models.entities import Agent, FraudAssessment
from app.models.verification_case import VerificationCase

from app.schemas.verification_api import (
    AdminAgentListResponse,
    AdminAgentRecordResponse,
    AgentVerificationResponse,
    AdminDashboardSummaryResponse,
    ReviewQueueResponse,
    ReviewerAccessEntry,
    ReviewerAccessListResponse,
    ReviewerAccessUpdateRequest,
    ReviewerCaseDetail,
    ReviewerFraudAssessment,
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
from app.core.reviewer_auth import require_admin, require_reviewer
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
from app.services.verification.admin_service import (
    AgentCategoryValidationError,
    ReviewerAccessValidationError,
    ReviewerAccountNotFoundError,
    VerificationAdministrationError,
    get_admin_dashboard_summary,
    list_agents_by_category,
    list_reviewer_access,
    update_reviewer_access,
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


def _reviewer_case_detail(
    db: Session,
    case: VerificationCase,
) -> ReviewerCaseDetail:
    """Attach only stored, reviewer-safe fraud evidence to a case."""

    detail = ReviewerCaseDetail.model_validate(case)
    assessment = db.execute(
        select(FraudAssessment)
        .where(FraudAssessment.verification_case_id == case.id)
        .order_by(FraudAssessment.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if assessment is None:
        return detail

    return detail.model_copy(
        update={
            "fraud_assessment": ReviewerFraudAssessment(
                id=assessment.id,
                risk_score=float(assessment.risk_score),
                risk_level=assessment.risk_level,
                model_version=assessment.model_version,
                requires_review=assessment.requires_review,
                signals=assessment.signals,
                created_at=assessment.created_at,
            )
        }
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
            _reviewer_case_detail(db, case)
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

    return _reviewer_case_detail(db, case)


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


# ---------------------------------------------------------
# Administrator dashboard and staff access management
# ---------------------------------------------------------

@router.get(
    "/admin/summary",
    response_model=AdminDashboardSummaryResponse,
)
def get_administrator_summary(
    db: Session = Depends(get_db),
    administrator_id: UUID = Depends(require_admin),
):
    summary = get_admin_dashboard_summary(db)
    return AdminDashboardSummaryResponse(
        awaiting_review_cases=summary.awaiting_review_cases,
        elevated_risk_cases=summary.elevated_risk_cases,
        new_cases_last_24_hours=summary.new_cases_last_24_hours,
        agents_under_review=summary.agents_under_review,
        active_reviewers=summary.active_reviewers,
        waiting_agents=summary.waiting_agents,
        approved_agents=summary.approved_agents,
        rejected_agents=summary.rejected_agents,
    )


@router.get(
    "/admin/agents/{category}",
    response_model=AdminAgentListResponse,
)
def get_administrator_agents_by_category(
    category: str,
    db: Session = Depends(get_db),
    administrator_id: UUID = Depends(require_admin),
):
    """Return agent profile details for one protected admin category."""

    try:
        agents = list_agents_by_category(db, category)
    except AgentCategoryValidationError as exc:
        raise HTTPException(status_code=404, detail="Agent category not found.") from exc

    return AdminAgentListResponse(
        category=category,
        agents=[
            AdminAgentRecordResponse(
                id=agent.id,
                user_id=agent.user_id,
                first_name=agent.first_name,
                last_name=agent.last_name,
                phone_number=agent.phone_number,
                date_of_birth=agent.date_of_birth,
                primary_residence=agent.primary_residence,
                nationality=agent.nationality,
                avatar_variant=agent.avatar_variant,
                status=agent.status.value,
                created_at=agent.created_at,
                updated_at=agent.updated_at,
            )
            for agent in agents
        ],
    )


@router.get(
    "/admin/reviewers",
    response_model=ReviewerAccessListResponse,
)
def get_administrator_reviewers(
    db: Session = Depends(get_db),
    administrator_id: UUID = Depends(require_admin),
):
    reviewers = list_reviewer_access(db)
    return ReviewerAccessListResponse(
        reviewers=[
            ReviewerAccessEntry(
                user_id=reviewer.user_id,
                is_active=reviewer.is_active,
                is_admin=reviewer.is_admin,
                created_at=reviewer.created_at,
            )
            for reviewer in reviewers
        ]
    )


@router.put(
    "/admin/reviewers/{user_id}",
    response_model=ReviewerAccessEntry,
)
def put_administrator_reviewer(
    user_id: UUID,
    payload: ReviewerAccessUpdateRequest,
    db: Session = Depends(get_db),
    administrator_id: UUID = Depends(require_admin),
):
    try:
        reviewer = update_reviewer_access(
            db=db,
            administrator_user_id=administrator_id,
            target_user_id=user_id,
            is_active=payload.is_active,
            is_admin=payload.is_admin,
        )
        return ReviewerAccessEntry(
            user_id=reviewer.user_id,
            is_active=reviewer.is_active,
            is_admin=reviewer.is_admin,
            created_at=reviewer.created_at,
        )
    except ReviewerAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReviewerAccessValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except VerificationAdministrationError as exc:
        raise HTTPException(
            status_code=500,
            detail="Reviewer access could not be updated.",
        ) from exc
