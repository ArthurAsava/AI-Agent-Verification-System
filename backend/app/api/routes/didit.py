from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.schemas.didit_api import (
    DiditSessionRequest,
    DiditSessionResponse,
    DiditWebhookResponse,
)
from app.services.didit_service import (
    DiditConfigurationError,
    DiditConflictError,
    DiditConsentRequiredError,
    DiditNotFoundError,
    DiditSubmissionError,
    DiditWebhookError,
    record_didit_webhook,
    start_didit_session,
)


router = APIRouter(prefix="/biometric/didit", tags=["Didit Biometric Provider"])
MAX_DIDIT_WEBHOOK_BODY_BYTES = 512 * 1024


@router.post("/sessions", response_model=DiditSessionResponse)
async def create_didit_session(
    payload: DiditSessionRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        session = await start_didit_session(
            db=db,
            user_id=user.id,
            biometric_consent=payload.biometric_consent,
        )
        return DiditSessionResponse(
            check_id=session.check_id,
            session_id=session.session_id,
            verification_url=session.verification_url,
            status=session.status,
        )
    except DiditConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Didit is not configured.") from exc
    except DiditNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiditConsentRequiredError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DiditConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DiditSubmissionError as exc:
        raise HTTPException(
            status_code=503,
            detail="Didit verification could not be started.",
        ) from exc


@router.post("/webhook", response_model=DiditWebhookResponse)
async def receive_didit_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        raw_body = await request.body()
        if len(raw_body) > MAX_DIDIT_WEBHOOK_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Webhook payload is too large.")
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid webhook payload.")

    try:
        status = record_didit_webhook(
            db=db,
            payload=payload,
            timestamp=request.headers.get("x-timestamp"),
            signature=request.headers.get("x-signature-v2"),
            previous_signature=request.headers.get("x-signature-v2-previous"),
        )
        return DiditWebhookResponse(status=status)
    except DiditConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Provider unavailable.") from exc
    except DiditWebhookError as exc:
        raise HTTPException(status_code=401, detail="Invalid provider callback.") from exc
    except DiditNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Provider session not found.") from exc
