from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.reviewer_auth import require_reviewer
from app.schemas.biometric_review_api import (
    BiometricProviderSummary,
    BiometricReviewDecisionRequest,
    BiometricReviewDecisionResponse,
    BiometricReviewItemResponse,
    BiometricReviewQueueResponse,
    ReviewerDocumentSummary,
)
from app.services.storage_service import (
    SupabaseStorageService,
    get_storage_service,
)
from app.services.verification.biometric_review_service import (
    BiometricReviewConflictError,
    BiometricReviewNotFoundError,
    BiometricReviewPersistenceError,
    BiometricReviewRetrievalError,
    BiometricReviewValidationError,
    download_biometric_review_document,
    list_pending_biometric_reviews,
    record_biometric_review_decision,
)


router = APIRouter(
    prefix="/verification/biometric-reviews",
    tags=["Biometric Reviews"],
)


def _to_document_summary(document) -> ReviewerDocumentSummary:
    return ReviewerDocumentSummary(
        document_id=document.document_id,
        document_type=document.document_type,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_size_bytes=document.file_size_bytes,
        status=document.status,
    )


def _to_provider_summary(summary) -> BiometricProviderSummary | None:
    if summary is None:
        return None
    return BiometricProviderSummary(
        provider=summary.provider,
        mode=summary.mode,
        submission_status=summary.submission_status,
        result_code=summary.result_code,
        result_text=summary.result_text,
        is_final=summary.is_final,
        actions=summary.actions,
    )


@router.get("", response_model=BiometricReviewQueueResponse)
def get_biometric_review_queue(
    db: Session = Depends(get_db),
    reviewer_id: UUID = Depends(require_reviewer),
):
    items = list_pending_biometric_reviews(db)
    return BiometricReviewQueueResponse(
        items=[
            BiometricReviewItemResponse(
                check_id=item.check_id,
                agent_id=item.agent_id,
                created_at=item.created_at,
                selfie=(
                    _to_document_summary(item.selfie)
                    if item.selfie is not None
                    else None
                ),
                identity_documents=[
                    _to_document_summary(document)
                    for document in item.identity_documents
                ],
                provider_summary=_to_provider_summary(item.provider_summary),
            )
            for item in items
        ]
    )


@router.get("/{check_id}/documents/{document_id}/download")
async def download_review_document(
    check_id: UUID,
    document_id: UUID,
    reviewer_id: UUID = Depends(require_reviewer),
    storage: SupabaseStorageService = Depends(get_storage_service),
):
    try:
        document, content = await download_biometric_review_document(
            reviewer_user_id=reviewer_id,
            check_id=check_id,
            document_id=document_id,
            storage=storage,
        )
    except BiometricReviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Review document not found.") from exc
    except BiometricReviewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BiometricReviewRetrievalError as exc:
        raise HTTPException(
            status_code=503,
            detail="Biometric review document is unavailable.",
        ) from exc

    media_type = document.mime_type or "application/octet-stream"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'inline; filename="review-document-{document.document_id}"'
            ),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/{check_id}/decision",
    response_model=BiometricReviewDecisionResponse,
)
def decide_biometric_review(
    check_id: UUID,
    payload: BiometricReviewDecisionRequest,
    db: Session = Depends(get_db),
    reviewer_id: UUID = Depends(require_reviewer),
):
    try:
        result = record_biometric_review_decision(
            db=db,
            check_id=check_id,
            reviewer_user_id=reviewer_id,
            action=payload.action,
            reason=payload.reason,
        )
        return BiometricReviewDecisionResponse(
            check_id=result.check_id,
            previous_status=result.previous_status,
            new_status=result.new_status,
            reviewed_at=result.reviewed_at,
        )
    except BiometricReviewNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Biometric review item not found.",
        ) from exc
    except BiometricReviewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BiometricReviewValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BiometricReviewPersistenceError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not save biometric review decision.",
        ) from exc
