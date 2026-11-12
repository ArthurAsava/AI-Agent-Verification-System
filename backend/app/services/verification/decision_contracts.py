
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CaseStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESUBMISSION_REQUIRED = "resubmission_required"
    ANALYSIS_FAILED = "analysis_failed"


class Recommendation(str, Enum):
    RECOMMEND_PASS = "recommend_pass"
    MANUAL_REVIEW = "manual_review"
    ESCALATE = "escalate"


class ReviewerAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_RESUBMISSION = "request_resubmission"


@dataclass(frozen=True)
class VerificationRecommendation:
    recommendation: Recommendation
    risk_score: int
    risk_level: str
    reason_codes: tuple[str, ...]
    requires_human_review: bool = True

    def __post_init__(self) -> None:
        if (
            type(self.risk_score) is not int
            or not 0 <= self.risk_score <= 100
        ):
            raise ValueError("Invalid risk score.")

        if not isinstance(
            self.recommendation, Recommendation
        ):
            raise ValueError("Invalid recommendation.")

        if not self.requires_human_review:
            raise ValueError(
                "Human verification is mandatory."
            )
