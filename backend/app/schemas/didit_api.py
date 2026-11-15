from __future__ import annotations

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
