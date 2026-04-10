"""add dining pass availability dates

Revision ID: j4k5l6m7n8o9
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "j4k5l6m7n8o9"
down_revision = "i3j4k5l6m7n8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dining_passes", sa.Column("available_from", sa.Date(), nullable=True))
    op.add_column("dining_passes", sa.Column("available_until", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("dining_passes", "available_until")
    op.drop_column("dining_passes", "available_from")
