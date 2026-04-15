"""add hero slider featured service fields

Revision ID: r2s3t4u5v6w7
Revises: q1r2s3t4u5v6
Create Date: 2026-04-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "r2s3t4u5v6w7"
down_revision = "q1r2s3t4u5v6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hero_sliders", sa.Column("highlight_text", sa.String(255), nullable=True))
    op.add_column("hero_sliders", sa.Column("features", JSONB, nullable=True))
    op.add_column("hero_sliders", sa.Column("featured_service_title", sa.String(255), nullable=True))
    op.add_column("hero_sliders", sa.Column("featured_service_description", sa.String(500), nullable=True))
    op.add_column("hero_sliders", sa.Column("featured_service_image", sa.String(500), nullable=True))
    op.add_column("hero_sliders", sa.Column("featured_service_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("hero_sliders", "featured_service_url")
    op.drop_column("hero_sliders", "featured_service_image")
    op.drop_column("hero_sliders", "featured_service_description")
    op.drop_column("hero_sliders", "featured_service_title")
    op.drop_column("hero_sliders", "features")
    op.drop_column("hero_sliders", "highlight_text")
