"""add meals_per_day field to dining_passes

Revision ID: l6m7n8o9p0q1
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "l6m7n8o9p0q1"
down_revision = "k5l6m7n8o9p0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dining_passes", sa.Column("meals_per_day", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("dining_passes", "meals_per_day")
