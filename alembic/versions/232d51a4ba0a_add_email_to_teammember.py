"""Add email to TeamMember

Revision ID: 232d51a4ba0a
Revises: 45ceb801fca4
Create Date: 2026-02-21 15:27:02.290525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '232d51a4ba0a'
down_revision: Union[str, None] = '45ceb801fca4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('team_members', sa.Column('email', sa.String(length=255), nullable=True))
    op.create_unique_constraint('uq_team_members_email', 'team_members', ['email'])


def downgrade() -> None:
    op.drop_constraint('uq_team_members_email', 'team_members', type_='unique')
    op.drop_column('team_members', 'email')
