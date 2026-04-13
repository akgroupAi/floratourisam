"""Add menu_categories table, category_id and nutritional_info to menu_items

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers
revision = "m7n8o9p0q1r2"
down_revision = "l6m7n8o9p0q1"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name=:table AND column_name=:column"
        ),
        {"table": table, "column": column},
    )
    return result.fetchone() is not None


def _table_exists(table):
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name=:table AND table_schema='public'"
        ),
        {"table": table},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    # Create menu_categories table if it doesn't exist
    if not _table_exists("menu_categories"):
        op.create_table(
            "menu_categories",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("restaurant_id", UUID(as_uuid=True), sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("meal_type", sa.String(50), nullable=True),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )

    # Add category_id FK column to menu_items
    if not _column_exists("menu_items", "category_id"):
        op.add_column(
            "menu_items",
            sa.Column("category_id", UUID(as_uuid=True), sa.ForeignKey("menu_categories.id", ondelete="SET NULL"), nullable=True),
        )

    # Add nutritional_info JSONB column to menu_items
    if not _column_exists("menu_items", "nutritional_info"):
        op.add_column("menu_items", sa.Column("nutritional_info", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("menu_items", "nutritional_info")
    op.drop_column("menu_items", "category_id")
    op.drop_table("menu_categories")
