"""add testimonial video fields

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
Create Date: 2026-04-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "u5v6w7x8y9z0"
down_revision = "t4u5v6w7x8y9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("testimonials", sa.Column("video_thumbnail", sa.String(500), nullable=True))
    op.add_column("testimonials", sa.Column("video_duration", sa.String(20), nullable=True))
    op.add_column("testimonials", sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("testimonials", "is_verified")
    op.drop_column("testimonials", "video_duration")
    op.drop_column("testimonials", "video_thumbnail")
