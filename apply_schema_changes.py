"""Apply database schema changes for nullable license_number"""
import asyncio
from sqlalchemy import text
from app.db.session import async_session_factory

async def apply_schema_changes():
    """Make doctor license_number nullable"""
    async with async_session_factory() as session:
        try:
            # Make license_number nullable
            await session.execute(text(
                "ALTER TABLE doctors ALTER COLUMN license_number DROP NOT NULL;"
            ))
            await session.commit()
            print("✓ Successfully made license_number nullable")
        except Exception as e:
            print(f"✗ Error applying schema changes: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(apply_schema_changes())
