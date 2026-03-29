"""Alembic migration: add medical packages and package items.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # medical_packages                                                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "medical_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        # timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # audit
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # soft delete
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        # core fields
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("short_description", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        # pricing
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("discounted_price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        # duration
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="1"),
        # optional links
        sa.Column("hospital_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        # media
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("gallery", postgresql.ARRAY(sa.String()), nullable=True),
        # flags
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("max_persons", sa.Integer(), nullable=False, server_default="1"),
        # content
        sa.Column("inclusions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("exclusions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("terms_and_conditions", sa.Text(), nullable=True),
        # seo
        sa.Column("meta_title", sa.String(255), nullable=True),
        sa.Column("meta_description", sa.String(500), nullable=True),
    )
    op.create_index("ix_medical_packages_slug", "medical_packages", ["slug"], unique=True)
    op.create_index("ix_medical_packages_category", "medical_packages", ["category"])
    op.create_index("ix_medical_packages_is_featured", "medical_packages", ["is_featured"])
    op.create_index("ix_medical_packages_hospital_id", "medical_packages", ["hospital_id"])
    op.create_index("ix_medical_packages_is_deleted", "medical_packages", ["is_deleted"])

    # ------------------------------------------------------------------ #
    # package_items                                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "package_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        # core
        sa.Column(
            "package_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medical_packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_package_items_package_id", "package_items", ["package_id"])
    op.create_index("ix_package_items_is_deleted", "package_items", ["is_deleted"])

    # ------------------------------------------------------------------ #
    # bookings — add package_id column                                    #
    # ------------------------------------------------------------------ #
    op.add_column(
        "bookings",
        sa.Column(
            "package_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medical_packages.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_bookings_package_id", "bookings", ["package_id"])


def downgrade() -> None:
    op.drop_index("ix_bookings_package_id", table_name="bookings")
    op.drop_column("bookings", "package_id")

    op.drop_index("ix_package_items_is_deleted", table_name="package_items")
    op.drop_index("ix_package_items_package_id", table_name="package_items")
    op.drop_table("package_items")

    op.drop_index("ix_medical_packages_is_deleted", table_name="medical_packages")
    op.drop_index("ix_medical_packages_hospital_id", table_name="medical_packages")
    op.drop_index("ix_medical_packages_is_featured", table_name="medical_packages")
    op.drop_index("ix_medical_packages_category", table_name="medical_packages")
    op.drop_index("ix_medical_packages_slug", table_name="medical_packages")
    op.drop_table("medical_packages")
