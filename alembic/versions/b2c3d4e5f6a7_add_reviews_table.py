"""Alembic migration: add reviews table.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        # ── Primary key ──────────────────────────────────────────────────────
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),

        # ── Polymorphic entity reference ─────────────────────────────────────
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),

        # ── Author ───────────────────────────────────────────────────────────
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),

        # ── Content ──────────────────────────────────────────────────────────
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("body", sa.Text, nullable=True),

        # ── Moderation ───────────────────────────────────────────────────────
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_approved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_featured", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("rejection_reason", sa.String(500), nullable=True),

        # ── Social ───────────────────────────────────────────────────────────
        sa.Column("helpful_count", sa.Integer, nullable=False, server_default=sa.text("0")),

        # ── Entity response ──────────────────────────────────────────────────
        sa.Column("response_text", sa.Text, nullable=True),
        sa.Column("response_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "response_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # ── Verification links ───────────────────────────────────────────────
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "consultation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consultations.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # ── Audit / soft-delete (BaseModel fields) ───────────────────────────
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),

        # ── Constraints ──────────────────────────────────────────────────────
        sa.UniqueConstraint("patient_id", "entity_type", "entity_id", name="uq_review_patient_entity"),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating_range"),
    )

    # ── Indexes ──────────────────────────────────────────────────────────────
    op.create_index("ix_reviews_entity", "reviews", ["entity_type", "entity_id"])
    op.create_index("ix_reviews_patient_id", "reviews", ["patient_id"])
    op.create_index("ix_reviews_is_approved", "reviews", ["is_approved"])
    op.create_index("ix_reviews_is_deleted", "reviews", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_reviews_is_deleted", table_name="reviews")
    op.drop_index("ix_reviews_is_approved", table_name="reviews")
    op.drop_index("ix_reviews_patient_id", table_name="reviews")
    op.drop_index("ix_reviews_entity", table_name="reviews")
    op.drop_table("reviews")
