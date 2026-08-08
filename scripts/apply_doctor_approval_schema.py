"""Apply doctor approval_status schema changes (production-safe).

Adds columns used by the doctor registration approval flow:
  - approval_status
  - rejection_reason
  - reviewed_at
  - reviewed_by

Also creates index/FK and backfills existing rows:
  is_verified=true  -> approval_status='approved'
  otherwise         -> approval_status='pending'

Usage (from project root, with production .env loaded):

    python scripts/apply_doctor_approval_schema.py

Safe to re-run (idempotent).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

# Allow `from app...` when run as a script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = (
    "approval_status",
    "rejection_reason",
    "reviewed_at",
    "reviewed_by",
)


async def _column_exists(conn, column_name: str) -> bool:
    result = await conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'doctors'
              AND column_name = :column_name
            """
        ),
        {"column_name": column_name},
    )
    return result.scalar() is not None


async def apply_schema() -> None:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    logger.info("Connecting to database...")

    try:
        async with engine.begin() as conn:
            # Ensure doctors table exists
            table_check = await conn.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'doctors'
                    """
                )
            )
            if table_check.scalar() is None:
                raise RuntimeError("Table 'doctors' not found. Aborting.")

            before = {
                col: await _column_exists(conn, col) for col in REQUIRED_COLUMNS
            }
            logger.info("Columns before: %s", before)

            # 1) Columns
            await conn.execute(
                text(
                    """
                    ALTER TABLE doctors
                    ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20)
                    NOT NULL DEFAULT 'pending'
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    ALTER TABLE doctors
                    ADD COLUMN IF NOT EXISTS rejection_reason TEXT
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    ALTER TABLE doctors
                    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITH TIME ZONE
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    ALTER TABLE doctors
                    ADD COLUMN IF NOT EXISTS reviewed_by UUID
                    """
                )
            )
            logger.info("Columns ensured.")

            # 2) Index
            await conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_doctors_approval_status
                    ON doctors (approval_status)
                    """
                )
            )
            logger.info("Index ix_doctors_approval_status ensured.")

            # 3) Foreign key (idempotent)
            fk_exists = await conn.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'fk_doctors_reviewed_by_users'
                    """
                )
            )
            if fk_exists.scalar() is None:
                await conn.execute(
                    text(
                        """
                        ALTER TABLE doctors
                        ADD CONSTRAINT fk_doctors_reviewed_by_users
                        FOREIGN KEY (reviewed_by)
                        REFERENCES users(id)
                        ON DELETE SET NULL
                        """
                    )
                )
                logger.info("FK fk_doctors_reviewed_by_users created.")
            else:
                logger.info("FK fk_doctors_reviewed_by_users already exists.")

            # 4) Backfill approval_status from is_verified
            result = await conn.execute(
                text(
                    """
                    UPDATE doctors
                    SET approval_status = CASE
                        WHEN is_verified = true THEN 'approved'
                        ELSE 'pending'
                    END
                    """
                )
            )
            logger.info("Backfill updated rows: %s", result.rowcount)

            # 5) Verification summary
            after = {
                col: await _column_exists(conn, col) for col in REQUIRED_COLUMNS
            }
            missing = [c for c, ok in after.items() if not ok]
            if missing:
                raise RuntimeError(f"Missing columns after migration: {missing}")

            counts = await conn.execute(
                text(
                    """
                    SELECT approval_status, COUNT(*) AS total
                    FROM doctors
                    GROUP BY approval_status
                    ORDER BY approval_status
                    """
                )
            )
            status_rows = counts.fetchall()
            logger.info("Columns after: %s", after)
            logger.info("approval_status counts: %s", dict(status_rows))
            logger.info("Doctor approval schema applied successfully.")
    finally:
        await engine.dispose()


def main() -> None:
    try:
        asyncio.run(apply_schema())
    except Exception as exc:
        logger.error("Failed to apply doctor approval schema: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
