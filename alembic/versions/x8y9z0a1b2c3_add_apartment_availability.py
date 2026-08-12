"""add apartment availability calendar and minimum stay

Apartments previously had only an is_available boolean — no way to block dates for
maintenance, set a seasonal rate, or require a minimum stay. This adds the per-date
calendar (mirroring room_availability, minus the unit count since an apartment is a
single unit) and a default minimum_nights on the apartment itself.

Existing apartments default to minimum_nights = 1, which is the current behaviour.

Revision ID: x8y9z0a1b2c3
Revises: w7x8y9z0a1b2
Create Date: 2026-08-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "x8y9z0a1b2c3"
down_revision = "w7x8y9z0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "apartments",
        sa.Column("minimum_nights", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "apartment_availability",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "apartment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("apartments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("minimum_nights", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        # BaseModel audit / soft-delete columns
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_apartment_availability_apartment_id", "apartment_availability", ["apartment_id"]
    )
    op.create_index("ix_apartment_availability_date", "apartment_availability", ["date"])
    # One live row per apartment per night; the calendar upsert relies on this.
    op.create_index(
        "uq_apartment_availability_apartment_date",
        "apartment_availability",
        ["apartment_id", "date"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("uq_apartment_availability_apartment_date", table_name="apartment_availability")
    op.drop_index("ix_apartment_availability_date", table_name="apartment_availability")
    op.drop_index("ix_apartment_availability_apartment_id", table_name="apartment_availability")
    op.drop_table("apartment_availability")
    op.drop_column("apartments", "minimum_nights")
