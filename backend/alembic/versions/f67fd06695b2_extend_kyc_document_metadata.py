"""extend kyc document metadata

Revision ID: f67fd06695b2
Revises: e66494f32ff5
Create Date: 2026-11-03 23:06:28.658665

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f67fd06695b2'
down_revision: Union[str, Sequence[str], None] = 'e66494f32ff5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Extend existing KYC document metadata."""

    op.add_column(
        "kyc_documents",
        sa.Column(
            "storage_bucket",
            sa.String(length=100),
            nullable=False,
            server_default="agent-kyc-documents",
        ),
    )

    op.add_column(
        "kyc_documents",
        sa.Column(
            "original_filename",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "kyc_documents",
        sa.Column(
            "mime_type",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "kyc_documents",
        sa.Column(
            "file_size_bytes",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "kyc_documents",
        sa.Column(
            "sha256_checksum",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "kyc_file_size_range",
        "kyc_documents",
        "file_size_bytes IS NULL OR "
        "(file_size_bytes > 0 AND file_size_bytes <= 5242880)",
    )

    op.create_check_constraint(
        "kyc_allowed_mime_type",
        "kyc_documents",
        "mime_type IS NULL OR mime_type IN "
        "('application/pdf', 'image/jpeg', 'image/png')",
    )


def downgrade() -> None:
    """Remove Phase 7 metadata extensions."""

    op.drop_constraint(
        "kyc_allowed_mime_type",
        "kyc_documents",
        type_="check",
    )

    op.drop_constraint(
        "kyc_file_size_range",
        "kyc_documents",
        type_="check",
    )

    op.drop_column(
        "kyc_documents",
        "sha256_checksum",
    )

    op.drop_column(
        "kyc_documents",
        "file_size_bytes",
    )

    op.drop_column(
        "kyc_documents",
        "mime_type",
    )

    op.drop_column(
        "kyc_documents",
        "original_filename",
    )

    op.drop_column(
        "kyc_documents",
        "storage_bucket",
    )

