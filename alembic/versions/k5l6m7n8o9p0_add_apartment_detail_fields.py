"""add apartment detail fields

Revision ID: k5l6m7n8o9p0
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY


# revision identifiers
revision = "k5l6m7n8o9p0"
down_revision = "j4k5l6m7n8o9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Type & Capacity
    op.add_column("apartments", sa.Column("property_type", sa.String(50), nullable=True))
    op.add_column("apartments", sa.Column("bedrooms", sa.Integer(), server_default="1", nullable=False))
    op.add_column("apartments", sa.Column("beds", sa.Integer(), server_default="1", nullable=False))
    op.add_column("apartments", sa.Column("bathrooms", sa.Integer(), server_default="1", nullable=False))

    # Contact
    op.add_column("apartments", sa.Column("phone", sa.String(20), nullable=True))
    op.add_column("apartments", sa.Column("email", sa.String(255), nullable=True))

    # Hospital proximity
    op.add_column("apartments", sa.Column("distance_to_hospital_km", sa.Float(), nullable=True))
    op.add_column("apartments", sa.Column("nearest_hospital", sa.String(255), nullable=True))

    # Medical amenities
    op.add_column("apartments", sa.Column("medical_amenities", ARRAY(sa.String), nullable=True))

    # Highlights
    op.add_column("apartments", sa.Column("highlights", JSONB(), nullable=True))

    # Policies
    op.add_column("apartments", sa.Column("check_in_time", sa.String(10), nullable=True))
    op.add_column("apartments", sa.Column("check_out_time", sa.String(10), nullable=True))
    op.add_column("apartments", sa.Column("house_rules", JSONB(), nullable=True))
    op.add_column("apartments", sa.Column("safety_features", JSONB(), nullable=True))
    op.add_column("apartments", sa.Column("cancellation_policy", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("apartments", "cancellation_policy")
    op.drop_column("apartments", "safety_features")
    op.drop_column("apartments", "house_rules")
    op.drop_column("apartments", "check_out_time")
    op.drop_column("apartments", "check_in_time")
    op.drop_column("apartments", "highlights")
    op.drop_column("apartments", "medical_amenities")
    op.drop_column("apartments", "nearest_hospital")
    op.drop_column("apartments", "distance_to_hospital_km")
    op.drop_column("apartments", "email")
    op.drop_column("apartments", "phone")
    op.drop_column("apartments", "bathrooms")
    op.drop_column("apartments", "beds")
    op.drop_column("apartments", "bedrooms")
    op.drop_column("apartments", "property_type")
