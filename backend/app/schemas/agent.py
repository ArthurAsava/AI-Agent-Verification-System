
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.entities import AgentStatus, AvatarVariant


class AgentCreate(BaseModel):
    first_name: str = Field(
        min_length=2, max_length=100
    )
    last_name: str = Field(
        min_length=2, max_length=100
    )
    phone_number: str | None = Field(
        default=None,
        min_length=7,
        max_length=30,
        pattern=r"^\+?[0-9][0-9 ()-]*$",
    )
    date_of_birth: date
    primary_residence: str = Field(min_length=2, max_length=255)
    nationality: str = Field(min_length=2, max_length=100)
    avatar_variant: AvatarVariant

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        if value >= date.today():
            raise ValueError("Date of birth must be in the past")
        return value


class AgentUpdate(BaseModel):
    first_name: str | None = Field(
        default=None, min_length=2, max_length=100
    )
    last_name: str | None = Field(
        default=None, min_length=2, max_length=100
    )
    phone_number: str | None = Field(
        default=None,
        min_length=7,
        max_length=30,
        pattern=r"^\+?[0-9][0-9 ()-]*$",
    )
    date_of_birth: date | None = None
    primary_residence: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )
    nationality: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )
    avatar_variant: AvatarVariant | None = None

    @field_validator("date_of_birth")
    @classmethod
    def validate_optional_date_of_birth(
        cls,
        value: date | None,
    ) -> date | None:
        if value is not None and value >= date.today():
            raise ValueError("Date of birth must be in the past")
        return value


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    first_name: str
    last_name: str
    phone_number: str | None
    date_of_birth: date | None
    primary_residence: str | None
    nationality: str | None
    avatar_variant: AvatarVariant | None
    status: AgentStatus
    created_at: datetime
    updated_at: datetime
