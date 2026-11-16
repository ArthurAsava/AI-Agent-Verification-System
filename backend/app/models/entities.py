
import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, Table

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AgentStatus(str, enum.Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class AvatarVariant(str, enum.Enum):
    """Server-controlled profile visual selected from a verified document."""

    MALE = "male"
    FEMALE = "female"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CheckStatus(str, enum.Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"

Table(
    "users",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    schema="auth",
    info={"external": True},
)

class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(30))
    avatar_variant: Mapped[AvatarVariant | None] = mapped_column(
        Enum(
            AvatarVariant,
            name="avatar_variant",
            values_callable=lambda e: [item.value for item in e],
        ),
        nullable=True,
    )
    status: Mapped[AgentStatus] = mapped_column(
        Enum(
            AgentStatus,
            name="agent_status",
            values_callable=lambda e: [item.value for item in e],
        ),
        nullable=False,
        server_default=AgentStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    documents: Mapped[list["KYCDocument"]] = relationship(
        back_populates="agent"
    )
    checks: Mapped[list["VerificationCheck"]] = relationship(
        back_populates="agent"
    )
    assessments: Mapped[list["FraudAssessment"]] = relationship(
        back_populates="agent"
    )



class KYCDocument(Base):
    __tablename__ = "kyc_documents"

    __table_args__ = (
        CheckConstraint(
            "file_size_bytes IS NULL OR "
            "(file_size_bytes > 0 AND file_size_bytes <= 5242880)",
            name="kyc_file_size_range",
        ),
        CheckConstraint(
            "mime_type IS NULL OR mime_type IN "
            "('application/pdf', 'image/jpeg', 'image/png')",
            name="kyc_allowed_mime_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )

    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    storage_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    storage_bucket: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        server_default="agent-kyc-documents",
    )

    original_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    file_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    sha256_checksum: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            values_callable=lambda e: [
                item.value for item in e
            ],
        ),
        nullable=False,
        server_default=DocumentStatus.PENDING.value,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    agent: Mapped["Agent"] = relationship(
        back_populates="documents"
    )

class VerificationCheck(Base):
    __tablename__ = "verification_checks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    check_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    status: Mapped[CheckStatus] = mapped_column(
        Enum(
            CheckStatus,
            name="check_status",
            values_callable=lambda e: [item.value for item in e],
        ),
        nullable=False,
        server_default=CheckStatus.PENDING.value,
    )
    result_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent: Mapped["Agent"] = relationship(back_populates="checks")


class FraudAssessment(Base):
    __tablename__ = "fraud_assessments"
    __table_args__ = (
        CheckConstraint(
            "risk_score >= 0 AND risk_score <= 100",
            name="risk_score_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    risk_score: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    risk_level: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    model_version: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    verification_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("verification_cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assessment_key: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    signals: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    requires_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent: Mapped["Agent"] = relationship(back_populates="assessments")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    action: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


Index("ix_kyc_documents_agent_id", KYCDocument.agent_id)
Index("ix_verification_checks_agent_id", VerificationCheck.agent_id)
Index("ix_fraud_assessments_agent_id", FraudAssessment.agent_id)
Index("ix_audit_logs_agent_id", AuditLog.agent_id)
