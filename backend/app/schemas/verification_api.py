
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.verification.contracts import FraudIndicator


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
    fraud_assessment: "ReviewerFraudAssessment | None" = None


class ReviewerFraudAssessment(BaseModel):
    """Reviewer-only, data-minimized explanation of a risk assessment."""

    id: UUID
    risk_score: float
    risk_level: str
    model_version: str
    requires_review: bool
    signals: list[FraudIndicator]
    created_at: datetime


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


class AdminDashboardSummaryResponse(BaseModel):
    awaiting_review_cases: int = Field(ge=0)
    elevated_risk_cases: int = Field(ge=0)
    new_cases_last_24_hours: int = Field(ge=0)
    agents_under_review: int = Field(ge=0)
    active_reviewers: int = Field(ge=0)
    waiting_agents: int = Field(ge=0)
    approved_agents: int = Field(ge=0)
    rejected_agents: int = Field(ge=0)


class AdminAgentRecordResponse(BaseModel):
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    phone_number: str | None
    date_of_birth: date | None
    primary_residence: str | None
    nationality: str | None
    avatar_variant: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class AdminAgentListResponse(BaseModel):
    category: Literal["waiting", "approved", "rejected"]
    agents: list[AdminAgentRecordResponse]


class ReviewerAccessEntry(BaseModel):
    user_id: UUID
    is_active: bool
    is_admin: bool
    created_at: datetime


class ReviewerAccessListResponse(BaseModel):
    reviewers: list[ReviewerAccessEntry]


class ReviewerAccessUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool
    is_admin: bool
