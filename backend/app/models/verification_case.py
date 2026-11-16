
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.entities import AvatarVariant


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VerificationCase(Base):
    __tablename__ = "verification_cases"

    __table_args__ = (
        UniqueConstraint(
            "processing_key",
            name="uq_verification_case_processing_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id"),
        nullable=False,
        index=True,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kyc_documents.id"),
        nullable=False,
        index=True,
    )

    processing_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending",
    )

    recommendation: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    risk_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    risk_level: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    scoring_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # A transient, server-generated candidate from the submitted document. It
    # becomes visible on the agent profile only after a reviewer approves.
    avatar_variant: Mapped[AvatarVariant | None] = mapped_column(
        Enum(
            AvatarVariant,
            name="avatar_variant",
            values_callable=lambda e: [item.value for item in e],
        ),
        nullable=True,
    )

    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True,
    )

    decision_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
