import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AccountSessionResponse(BaseModel):
    """A safe, user-owned view of a Supabase Auth session record."""

    id: uuid.UUID
    created_at: datetime | None
    last_active_at: datetime | None
    expires_at: datetime | None
    user_agent: str | None = Field(default=None, max_length=180)
    is_current: bool
