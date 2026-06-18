"""add hero slider icon field

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-06-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "l7m8n9o0p1q2"
down_revision = "k6l7m8n9o0p1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hero_sliders", sa.Column("icon", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("hero_sliders", "icon")
