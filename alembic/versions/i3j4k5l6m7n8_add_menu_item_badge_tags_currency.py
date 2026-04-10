"""Add menu item badge, tags, and currency columns.

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-04-10 17:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers
revision = "i3j4k5l6m7n8"
down_revision = "h2i3j4k5l6m7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("menu_items", sa.Column("badge", sa.String(50), nullable=True))
    op.add_column("menu_items", sa.Column("tags", ARRAY(sa.String), nullable=True))
    op.add_column("menu_items", sa.Column("currency", sa.String(3), server_default="USD", nullable=False))


def downgrade() -> None:
    op.drop_column("menu_items", "currency")
    op.drop_column("menu_items", "tags")
    op.drop_column("menu_items", "badge")
