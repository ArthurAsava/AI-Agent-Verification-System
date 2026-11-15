
from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import Response
from app.services.kyc_retrieval_service import (
    DocumentInfo,
    DocumentNotFoundError,
    DocumentRetrievalError,
    list_agent_documents,
    get_agent_document,
    download_agent_document,
)

# Adjust these two imports to your existing project.
from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db

from app.services.file_validation import (
    FileValidationError,
    MAX_FILE_SIZE,
)
from app.services.kyc_upload_service import (
    AgentNotFoundError,
    BiometricConsentRequiredError,
    DocumentCleanupError,
    DocumentUploadError,
    InvalidDocumentTypeError,
    upload_biometric_selfie,
    upload_kyc_document,
)
from app.services.storage_service import (
    StorageConfigurationError,
    SupabaseStorageService,
    get_storage_service,
)


router = APIRouter(
    prefix="/kyc/documents",
    tags=["KYC Documents"],
)


class KYCDocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    agent_id: uuid.UUID
    document_type: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    status: str
    biometric_check_id: uuid.UUID | None = None


async def _read_upload_content(file: UploadFile) -> bytes:
    """Read one bounded upload and always release its temporary file."""

    try:
        content = await file.read(MAX_FILE_SIZE + 1)
    finally:
        await file.close()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File exceeds the 5 MiB limit.",
        )

    return content


def _to_upload_response(result) -> KYCDocumentUploadResponse:
    return KYCDocumentUploadResponse(
        document_id=result.document_id,
        agent_id=result.agent_id,
        document_type=result.document_type,
        original_filename=result.original_filename,
        mime_type=result.mime_type,
        file_size_bytes=result.file_size_bytes,
        status=result.status,
        biometric_check_id=result.biometric_check_id,
    )


@router.post(
    "",
    response_model=KYCDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_kyc_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: SupabaseStorageService = Depends(
        get_storage_service
    ),
):
    """
    Upload one KYC document for the authenticated agent.
    """

    user_id = user.id

    content = await _read_upload_content(file)

    try:
        result = await upload_kyc_document(
            db=db,
            storage=storage,
            user_id=user_id,
            document_type=document_type,
            filename=file.filename or "",
            content=content,
            declared_content_type=file.content_type,
        )

    except InvalidDocumentTypeError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except FileValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except StorageConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Document storage is unavailable.",
        ) from exc

    except DocumentCleanupError as exc:
        # Log this server-side and alert administrators.
        raise HTTPException(
            status_code=500,
            detail=(
                "Document processing failed. "
                "Please contact support."
            ),
        ) from exc

    except DocumentUploadError as exc:
        raise HTTPException(
            status_code=503,
            detail="Document upload could not be completed.",
        ) from exc

    return _to_upload_response(result)


@router.post(
    "/biometric-selfie",
    response_model=KYCDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_biometric_selfie(
    consent: bool = Form(...),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: SupabaseStorageService = Depends(get_storage_service),
):
    """Capture a consented selfie for a human biometric review.

    Liveness and face-match results are deliberately not inferred from a
    single image. Those assessments remain manual until an approved biometric
    provider is integrated.
    """

    if consent is not True:
        raise HTTPException(
            status_code=422,
            detail=(
                "Explicit consent is required before capturing a biometric selfie."
            ),
        )

    content = await _read_upload_content(file)

    try:
        result = await upload_biometric_selfie(
            db=db,
            storage=storage,
            user_id=user.id,
            consent=consent,
            filename=file.filename or "",
            content=content,
            declared_content_type=file.content_type,
        )
    except FileValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except BiometricConsentRequiredError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except StorageConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Document storage is unavailable.",
        ) from exc
    except DocumentCleanupError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Biometric capture could not be secured. Please contact support."
            ),
        ) from exc
    except DocumentUploadError as exc:
        raise HTTPException(
            status_code=503,
            detail="Biometric capture could not be stored.",
        ) from exc

    return _to_upload_response(result)


class KYCDocumentResponse(BaseModel):
    document_id: uuid.UUID
    agent_id: uuid.UUID
    document_type: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    status: str


def to_document_response(
    document: DocumentInfo,
) -> KYCDocumentResponse:
    return KYCDocumentResponse(
        document_id=document.id,
        agent_id=document.agent_id,
        document_type=document.document_type,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_size_bytes=document.file_size_bytes,
        status=document.status,
    )


@router.get(
    "",
    response_model=list[KYCDocumentResponse],
)
async def list_kyc_documents(
    user: CurrentUser = Depends(get_current_user),
):
    try:
        documents = await list_agent_documents(user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        ) from exc

    return [
        to_document_response(document)
        for document in documents
    ]


@router.get(
    "/{document_id}",
    response_model=KYCDocumentResponse,
)
async def get_kyc_document(
    document_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        document = await get_agent_document(
            user.id,
            document_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        ) from exc

    return to_document_response(document)


@router.get("/{document_id}/download")
async def download_kyc_document(
    document_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    storage: SupabaseStorageService = Depends(get_storage_service),
):
    try:
        document, content = await download_agent_document(
            user_id=user.id,
            document_id=document_id,
            storage=storage,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        ) from exc
    except DocumentRetrievalError as exc:
        raise HTTPException(
            status_code=503,
            detail="Document download is unavailable.",
        ) from exc

    return Response(
        content=content,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="kyc-document-{document.id}"'
            ),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
