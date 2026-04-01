"""Merge multiple heads into a single head.

Revision ID: f9a8b7c6d5e4
Revises: 232d51a4ba0a, e5f6a7b8c9d0
Create Date: 2026-04-01 23:25:00

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = 'f9a8b7c6d5e4'
down_revision: Union[str, Sequence[str], None] = ('232d51a4ba0a', 'e5f6a7b8c9d0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge migration — no schema changes needed.
    pass


def downgrade() -> None:
    pass
