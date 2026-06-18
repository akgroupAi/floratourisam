"""make doctors.verification_date timezone-aware

Fixes: asyncpg DataError "can't subtract offset-naive and offset-aware
datetimes" when verifying a doctor — the column was TIMESTAMP WITHOUT TIME
ZONE while the app writes timezone-aware UTC datetimes.

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-06-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "m8n9o0p1q2r3"
down_revision = "l7m8n9o0p1q2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Interpret existing naive values as UTC.
    op.alter_column(
        "doctors",
        "verification_date",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        existing_nullable=True,
        postgresql_using="verification_date AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "doctors",
        "verification_date",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="verification_date AT TIME ZONE 'UTC'",
    )
