"""Initialize database schema and stamp Alembic head."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.base import Base
import app.models  # Import all models to register with Base
from app.core.config import settings
import subprocess

async def init_db():
    print(f"Connecting to database: {settings.DATABASE_URL}")
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        print("Creating all tables from metadata...")
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    print("✓ Successfully created database tables.")
    
    print("Stamping Alembic head (f9a8b7c6d5e4)...")
    try:
        # Run alembic stamp to mark it as head
        subprocess.run(
            ["env/bin/python", "-m", "alembic", "stamp", "f9a8b7c6d5e4"],
            check=True,
            capture_output=True,
            text=True
        )
        print("✓ Successfully stamped Alembic head.")
    except subprocess.CalledProcessError as e:
        print(f"✗ Error stamping Alembic head: {e.stderr}")
        raise

if __name__ == "__main__":
    asyncio.run(init_db())
