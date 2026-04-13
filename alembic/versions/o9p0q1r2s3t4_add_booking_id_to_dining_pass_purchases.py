"""Add booking_id to dining_pass_purchases."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'o9p0q1r2s3t4'
down_revision = 'n8o9p0q1r2s3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'dining_pass_purchases',
        sa.Column('booking_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_dining_pass_purchases_booking_id',
        'dining_pass_purchases', 'bookings',
        ['booking_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        op.f('ix_dining_pass_purchases_booking_id'),
        'dining_pass_purchases', ['booking_id'], unique=False,
    )


def downgrade():
    op.drop_index(op.f('ix_dining_pass_purchases_booking_id'), table_name='dining_pass_purchases')
    op.drop_constraint('fk_dining_pass_purchases_booking_id', 'dining_pass_purchases', type_='foreignkey')
    op.drop_column('dining_pass_purchases', 'booking_id')
