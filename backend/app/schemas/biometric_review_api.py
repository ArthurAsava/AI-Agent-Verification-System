from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReviewerDocumentSummary(BaseModel):
    document_id: UUID
    document_type: str
    original_filename: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    status: str


class BiometricProviderSummary(BaseModel):
    provider: str
    mode: str
    submission_status: str
    result_code: str | None = None
    result_text: str | None = None
    is_final: bool | None = None
    actions: dict[str, str] = Field(default_factory=dict)


class BiometricReviewItemResponse(BaseModel):
    check_id: UUID
    agent_id: UUID
    created_at: datetime | None = None
    selfie: ReviewerDocumentSummary | None = None
    identity_documents: list[ReviewerDocumentSummary]
    provider_summary: BiometricProviderSummary | None = None


class BiometricReviewQueueResponse(BaseModel):
    items: list[BiometricReviewItemResponse]


class BiometricReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal[
        "confirm_match",
        "request_resubmission",
        "reject_capture",
    ]
    reason: str = Field(min_length=10, max_length=1000)


class BiometricReviewDecisionResponse(BaseModel):
    check_id: UUID
    previous_status: str
    new_status: str
    reviewed_at: datetime
