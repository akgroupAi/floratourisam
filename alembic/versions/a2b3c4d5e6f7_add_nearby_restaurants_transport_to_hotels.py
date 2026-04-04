"""Add nearby_restaurants and nearby_transport JSONB columns to hotels.

Revision ID: a2b3c4d5e6f7
Revises: f9a8b7c6d5e4
Create Date: 2026-04-04 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'f9a8b7c6d5e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('hotels', sa.Column('nearby_restaurants', JSONB, nullable=True))
    op.add_column('hotels', sa.Column('nearby_transport', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('hotels', 'nearby_transport')
    op.drop_column('hotels', 'nearby_restaurants')
