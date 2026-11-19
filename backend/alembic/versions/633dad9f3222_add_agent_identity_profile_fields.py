"""add agent identity profile fields

Revision ID: 633dad9f3222
Revises: d8e4f9a1c2b7
Create Date: 2026-11-18 07:14:23.116683

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "633dad9f3222"
down_revision = "d8e4f9a1c2b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store the identity details required before document verification."""
    op.add_column(
        "agents",
        sa.Column("date_of_birth", sa.Date(), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("primary_residence", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("nationality", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    """Remove the identity profile fields on an explicit rollback."""
    op.drop_column("agents", "nationality")
    op.drop_column("agents", "primary_residence")
    op.drop_column("agents", "date_of_birth")
