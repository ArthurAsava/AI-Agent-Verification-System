
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VerificationAnalysisResponse(BaseModel):
    case_id: UUID
    status: str
    message: str


class VerificationCaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    document_id: UUID
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class AgentVerificationResponse(BaseModel):
    cases: list[VerificationCaseSummary]


class ReviewerCaseDetail(VerificationCaseSummary):
    recommendation: str | None = None
    risk_score: int | None = None
    risk_level: str | None = None
    scoring_version: str | None = None
    reviewer_user_id: UUID | None = None
    decision_reason: str | None = None
    reviewed_at: datetime | None = None


class ReviewQueueResponse(BaseModel):
    cases: list[ReviewerCaseDetail]


class VerificationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal[
        "approve",
        "reject",
        "request_resubmission",
    ]

    reason: str = Field(
        min_length=10,
        max_length=1000,
    )

    expected_version: int = Field(ge=0)


class VerificationDecisionResponse(BaseModel):
    case_id: UUID
    previous_status: str
    new_status: str
    version: int
    reviewed_at: datetime
