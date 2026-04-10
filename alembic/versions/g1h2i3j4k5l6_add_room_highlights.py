"""add_room_highlights

Revision ID: g1h2i3j4k5l6
Revises: 1ac138c6d39d
Create Date: 2026-04-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, None] = '1ac138c6d39d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rooms', sa.Column('highlights', ARRAY(sa.String()), nullable=True))


def downgrade() -> None:
    op.drop_column('rooms', 'highlights')
