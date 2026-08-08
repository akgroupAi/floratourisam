"""Add doctor approval_status and review audit fields.

Revision ID: o0p1q2r3s4t5
Revises: n9o0p1q2r3s4
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa


revision = "o0p1q2r3s4t5"
down_revision = "n9o0p1q2r3s4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE doctors ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20) NOT NULL DEFAULT 'pending'"
    )
    op.execute("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS rejection_reason TEXT")
    op.execute(
        "ALTER TABLE doctors ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITH TIME ZONE"
    )
    op.execute("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS reviewed_by UUID")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_doctors_approval_status ON doctors (approval_status)"
    )
    op.execute(
        """
        DO $outer$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'fk_doctors_reviewed_by_users'
          ) THEN
            ALTER TABLE doctors
              ADD CONSTRAINT fk_doctors_reviewed_by_users
              FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL;
          END IF;
        END
        $outer$;
        """
    )
    op.execute(
        """
        UPDATE doctors
        SET approval_status = CASE
            WHEN is_verified = true THEN 'approved'
            ELSE 'pending'
        END
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE doctors DROP CONSTRAINT IF EXISTS fk_doctors_reviewed_by_users"
    )
    op.execute("DROP INDEX IF EXISTS ix_doctors_approval_status")
    op.drop_column("doctors", "reviewed_by")
    op.drop_column("doctors", "reviewed_at")
    op.drop_column("doctors", "rejection_reason")
    op.drop_column("doctors", "approval_status")
