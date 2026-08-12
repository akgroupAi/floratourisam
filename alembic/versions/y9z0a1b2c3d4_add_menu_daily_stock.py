"""add daily stock to menu items

is_available is a permanent on/off switch. These columns are the per-service
equivalent: a daily quantity, a counter, and the date that counter refers to.

NULL daily_quantity means unlimited, which is the existing behaviour, so nothing
changes for current menu items until a quantity is set.

Revision ID: y9z0a1b2c3d4
Revises: x8y9z0a1b2c3
Create Date: 2026-08-12

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "y9z0a1b2c3d4"
down_revision = "x8y9z0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("menu_items", sa.Column("daily_quantity", sa.Integer(), nullable=True))
    op.add_column(
        "menu_items",
        sa.Column("sold_today", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("menu_items", sa.Column("stock_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("menu_items", "stock_date")
    op.drop_column("menu_items", "sold_today")
    op.drop_column("menu_items", "daily_quantity")
