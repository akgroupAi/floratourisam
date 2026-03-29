"""Alembic migration: add patient_favorites table.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_favorites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # core
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        # unique: one record per (patient, type, entity)
        sa.UniqueConstraint("patient_id", "entity_type", "entity_id", name="uq_patient_favorite"),
    )
    op.create_index("ix_patient_favorites_patient_id", "patient_favorites", ["patient_id"])
    op.create_index("ix_patient_favorites_entity_type", "patient_favorites", ["entity_type"])
    op.create_index(
        "ix_patient_favorites_patient_type",
        "patient_favorites",
        ["patient_id", "entity_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_patient_favorites_patient_type", table_name="patient_favorites")
    op.drop_index("ix_patient_favorites_entity_type", table_name="patient_favorites")
    op.drop_index("ix_patient_favorites_patient_id", table_name="patient_favorites")
    op.drop_table("patient_favorites")
