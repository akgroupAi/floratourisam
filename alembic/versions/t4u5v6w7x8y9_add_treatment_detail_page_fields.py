"""add treatment detail page fields

Revision ID: t4u5v6w7x8y9
Revises: s3t4u5v6w7x8
Create Date: 2026-04-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "t4u5v6w7x8y9"
down_revision = "s3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("treatments", sa.Column("recovery_text", sa.String(100), nullable=True))
    op.add_column("treatments", sa.Column("why_choose", JSONB, nullable=True))
    op.add_column("treatments", sa.Column("available_treatments", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("treatments", "available_treatments")
    op.drop_column("treatments", "why_choose")
    op.drop_column("treatments", "recovery_text")
