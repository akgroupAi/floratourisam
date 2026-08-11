"""add platform_fee to bookings

Records the platform fee charged to the customer on top of the booking subtotal. The
fee is already included in total_price; this column stores the portion so a receipt can
itemise it.

Existing rows default to 0 and their total_price is left untouched — those bookings were
quoted and in many cases already paid without a fee, so back-filling one would rewrite
history and misstate what customers actually owed.

Revision ID: w7x8y9z0a1b2
Revises: o0p1q2r3s4t5
Create Date: 2026-08-11

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "w7x8y9z0a1b2"
down_revision = "o0p1q2r3s4t5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column(
            "platform_fee",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("bookings", "platform_fee")
