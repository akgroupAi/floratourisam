"""add cancellation charge and refund workflow to bookings

Cancelling a paid booking previously wrote a hardcoded 80% into refund_amount and
nothing ever paid it. These columns back a real workflow: the policy computes the
refund, the booking enters a pending queue, and an admin releases it to Razorpay.

Existing bookings default to refund_status = 'none', so nothing already cancelled is
retroactively pulled into the queue. Anything cancelled before this deploy that is owed
money needs handling by hand — see REFUND_POLICY.md.

Revision ID: a1b2c3d4e5f6
Revises: z0a1b2c3d4e5
Create Date: 2026-08-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "a1b2c3d4e5f6"
down_revision = "z0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("cancellation_charge", sa.Float(), nullable=True))
    op.add_column(
        "bookings",
        sa.Column("refund_status", sa.String(20), nullable=False, server_default="none"),
    )
    op.add_column(
        "bookings", sa.Column("refund_requested_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "bookings", sa.Column("refund_processed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "bookings",
        sa.Column("refund_processed_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("bookings", sa.Column("refund_reference", sa.String(100), nullable=True))
    op.add_column("bookings", sa.Column("refund_note", sa.String(500), nullable=True))

    # The pending queue is read on every admin page load.
    op.create_index("ix_bookings_refund_status", "bookings", ["refund_status"])


def downgrade() -> None:
    op.drop_index("ix_bookings_refund_status", table_name="bookings")
    for column in (
        "refund_note",
        "refund_reference",
        "refund_processed_by",
        "refund_processed_at",
        "refund_requested_at",
        "refund_status",
        "cancellation_charge",
    ):
        op.drop_column("bookings", column)
