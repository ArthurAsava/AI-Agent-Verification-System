
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VerificationOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudIndicator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    severity: RiskLevel
    evidence: dict[str, Any] = Field(default_factory=dict)


class DocumentAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    document_type: str = Field(min_length=1, max_length=50)
    outcome: VerificationOutcome
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    analyzer_version: str = Field(min_length=1, max_length=50)


class RiskAssessmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    risk_score: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    model_version: str = Field(min_length=1, max_length=50)
    indicators: list[FraudIndicator] = Field(default_factory=list)
    requires_review: bool = True
