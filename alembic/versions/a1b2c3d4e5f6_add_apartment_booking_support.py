"""add apartment booking support

Revision ID: a1b2c3d4e5f6
Revises: 213a1f91540c
Create Date: 2026-03-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '213a1f91540c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'bookings',
        sa.Column(
            'apartment_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('apartments.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index('ix_bookings_apartment_id', 'bookings', ['apartment_id'])


def downgrade() -> None:
    op.drop_index('ix_bookings_apartment_id', table_name='bookings')
    op.drop_column('bookings', 'apartment_id')
