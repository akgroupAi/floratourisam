"""Add hospitality_services and hospitality_pages tables.

Revision ID: k6l7m8n9o0p1
Revises: n5o6p7q8r9s0
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = "k6l7m8n9o0p1"
down_revision = "n2o3p4q5r6s7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hospitality_services",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("icon", sa.String(100), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("highlight", sa.String(100), nullable=True),
        sa.Column("url", sa.String(255), nullable=True),
        sa.Column("display_order", sa.Integer, default=0),
        sa.Column("is_active", sa.Boolean, default=True),
        # BaseModel audit / soft-delete columns
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", UUID(as_uuid=True), nullable=True),
    )

    op.create_table(
        "hospitality_pages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("service_id", UUID(as_uuid=True), sa.ForeignKey("hospitality_services.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False, index=True),
        # Hero
        sa.Column("hero_title", sa.String(255), nullable=False),
        sa.Column("hero_subtitle", sa.Text, nullable=True),
        sa.Column("hero_background_image", sa.String(500), nullable=True),
        sa.Column("hero_breadcrumb", JSONB, nullable=True),
        sa.Column("hero_ctas", JSONB, nullable=True),
        # Stats
        sa.Column("stats", JSONB, nullable=True),
        # Features
        sa.Column("features_title", sa.String(255), nullable=True),
        sa.Column("features_subtitle", sa.String(500), nullable=True),
        sa.Column("features", JSONB, nullable=True),
        # Steps
        sa.Column("steps_title", sa.String(255), nullable=True),
        sa.Column("steps_subtitle", sa.String(500), nullable=True),
        sa.Column("steps", JSONB, nullable=True),
        # Gallery
        sa.Column("gallery_title", sa.String(255), nullable=True),
        sa.Column("gallery_subtitle", sa.String(500), nullable=True),
        sa.Column("gallery_images", JSONB, nullable=True),
        # Testimonials
        sa.Column("testimonials_title", sa.String(255), nullable=True),
        sa.Column("testimonials_subtitle", sa.String(500), nullable=True),
        sa.Column("testimonial_category", sa.String(100), nullable=True),
        # FAQ
        sa.Column("faq_title", sa.String(255), nullable=True),
        sa.Column("faq_category", sa.String(100), nullable=True),
        # SEO
        sa.Column("meta_title", sa.String(255), nullable=True),
        sa.Column("meta_description", sa.String(500), nullable=True),
        # Extra
        sa.Column("extra_sections", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        # BaseModel audit / soft-delete columns
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("hospitality_pages")
    op.drop_table("hospitality_services")
