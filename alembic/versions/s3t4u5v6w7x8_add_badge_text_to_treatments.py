"""add badge_text to treatments

Revision ID: s3t4u5v6w7x8
Revises: r2s3t4u5v6w7
Create Date: 2026-04-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "s3t4u5v6w7x8"
down_revision = "r2s3t4u5v6w7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("treatments", sa.Column("badge_text", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("treatments", "badge_text")
