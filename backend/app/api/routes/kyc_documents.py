
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

# Adjust these two imports to your existing project.
from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db

from app.services.file_validation import (
    FileValidationError,
    MAX_FILE_SIZE,
)
from app.services.kyc_upload_service import (
    AgentNotFoundError,
    DocumentCleanupError,
    DocumentUploadError,
    InvalidDocumentTypeError,
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

    # Read no more than 5 MiB plus one byte.
    # An extra byte lets us detect oversized files.
    try:
        content = await file.read(MAX_FILE_SIZE + 1)
    finally:
        await file.close()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File exceeds the 5 MiB limit.",
        )

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

    return KYCDocumentUploadResponse(
        document_id=result.document_id,
        agent_id=result.agent_id,
        document_type=result.document_type,
        original_filename=result.original_filename,
        mime_type=result.mime_type,
        file_size_bytes=result.file_size_bytes,
        status=result.status,
    )
