from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class DiditSessionRequest(BaseModel):
    """The explicit consent collected immediately before a hosted flow."""

    biometric_consent: Literal[True]


class DiditSessionResponse(BaseModel):
    check_id: UUID
    provider: Literal["didit"] = "didit"
    session_id: str
    verification_url: str
    status: str


class DiditWebhookResponse(BaseModel):
    status: str


class DiditKycStatus(BaseModel):
    check_id: UUID
    check_status: str
    provider_status: str | None = None
    is_final: bool | None = None
    actions: dict[str, str]
    synced_at: datetime | None = None


class DiditKycStatusResponse(BaseModel):
    check: DiditKycStatus | None = None
