
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import AgentStatus


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


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    first_name: str
    last_name: str
    phone_number: str | None
    status: AgentStatus
    created_at: datetime
    updated_at: datetime
