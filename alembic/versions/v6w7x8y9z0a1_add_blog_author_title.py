"""add blog author_title field

Revision ID: v6w7x8y9z0a1
Revises: u5v6w7x8y9z0
Create Date: 2026-04-16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "v6w7x8y9z0a1"
down_revision = "u5v6w7x8y9z0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("blog_posts", sa.Column("author_title", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("blog_posts", "author_title")
