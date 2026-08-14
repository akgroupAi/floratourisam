"""add booking guests and documents

Bookings previously carried only a guest_count and a free-form guest_details blob.
Medical travel needs the real thing: who is travelling, their passport details, and
scanned documents — flight tickets, passport photos, visas, insurance.

booking_guests holds one row per traveller (the patient plus any companions).
booking_documents holds uploaded files, optionally attached to a specific traveller
since a passport belongs to a person while a shared flight booking does not.

Existing bookings are untouched: they simply have no guest or document rows, and
guest_details is left in place for anything already stored there.

Revision ID: z0a1b2c3d4e5
Revises: y9z0a1b2c3d4
Create Date: 2026-08-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "z0a1b2c3d4e5"
down_revision = "y9z0a1b2c3d4"
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "booking_guests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("guest_type", sa.String(20), nullable=False, server_default="companion"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column("passport_number", sa.String(50), nullable=True),
        sa.Column("passport_expiry", sa.Date(), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("relationship_to_patient", sa.String(50), nullable=True),
        sa.Column("special_needs", sa.Text(), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_booking_guests_booking_id", "booking_guests", ["booking_id"])

    op.create_table(
        "booking_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "guest_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("booking_guests.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_booking_documents_booking_id", "booking_documents", ["booking_id"])
    op.create_index("ix_booking_documents_guest_id", "booking_documents", ["guest_id"])


def downgrade() -> None:
    op.drop_index("ix_booking_documents_guest_id", table_name="booking_documents")
    op.drop_index("ix_booking_documents_booking_id", table_name="booking_documents")
    op.drop_table("booking_documents")
    op.drop_index("ix_booking_guests_booking_id", table_name="booking_guests")
    op.drop_table("booking_guests")
