"""add_buy_sell_rates_to_currency

Revision ID: b27a85a95232
Revises: 0701fa325cae
Create Date: 2026-04-07 23:00:27.073411

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b27a85a95232'
down_revision: Union[str, None] = '0701fa325cae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('currencies', sa.Column('buy_rate', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('currencies', sa.Column('sell_rate', sa.Float(), nullable=False, server_default='0.0'))


def downgrade() -> None:
    op.drop_column('currencies', 'sell_rate')
    op.drop_column('currencies', 'buy_rate')
