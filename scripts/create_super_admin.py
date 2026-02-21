"""Script to create a super admin user."""
import asyncio
import logging
import sys
import os

# Add to path to allow importing app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import async_session_factory
from app.models.user import User
from app.utils.enums import UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_super_admin(email: str, password: str, full_name: str = "Super Admin"):
    async with async_session_factory() as session:
        # Check if exists
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            logger.info(f"User with email {email} already exists. Updating role to SUPER_ADMIN...")
            user.role = UserRole.SUPER_ADMIN.value
            await session.commit()
            logger.info("Updated existing user successfully.")
            return

        # Create user
        new_user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role=UserRole.SUPER_ADMIN.value,
            is_active=True,
            is_verified=True,
        )
        session.add(new_user)
        await session.commit()
        logger.info(f"Super admin user {email} created successfully.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/create_super_admin.py <email> <password> [full_name]")
        sys.exit(1)
        
    email = sys.argv[1]
    password = sys.argv[2]
    full_name = sys.argv[3] if len(sys.argv) > 3 else "Super Admin"
    
    asyncio.run(create_super_admin(email, password, full_name))
