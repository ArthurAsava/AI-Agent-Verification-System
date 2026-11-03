
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ExperienceLevel = Literal[
    "beginner",
    "intermediate",
    "experienced",
]


class OnboardingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    county: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    city: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    business_name: str | None = Field(
        default=None,
        max_length=150,
    )

    experience_level: ExperienceLevel | None = None

    preferred_sales_category: str | None = Field(
        default=None,
        max_length=100,
    )


class OnboardingProgress(BaseModel):
    completed_fields: int
    total_fields: int
    percentage: int
    missing_fields: list[str]
    profile_complete: bool


class OnboardingResponse(BaseModel):
    agent_id: str

    first_name: str
    last_name: str
    phone_number: str | None

    county: str | None
    city: str | None
    business_name: str | None
    experience_level: str | None
    preferred_sales_category: str | None

    agent_status: str
    progress: OnboardingProgress
