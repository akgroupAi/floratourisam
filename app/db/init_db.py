"""Database initialization and seeding."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.models.user import User
from app.utils.enums import UserRole

logger = get_logger(__name__)


async def init_database(db: AsyncSession) -> None:
    """Initialize database with default data.

    Creates the first superuser if it doesn't exist.

    Args:
        db: Database session.
    """
    # Check if superuser exists
    result = await db.execute(
        select(User).where(User.email == settings.FIRST_SUPERUSER_EMAIL)
    )
    superuser = result.scalar_one_or_none()

    if superuser is None:
        # Create superuser
        superuser = User(
            email=settings.FIRST_SUPERUSER_EMAIL,
            hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
            full_name="System Administrator",
            role=UserRole.SUPER_ADMIN.value,
            is_active=True,
            is_verified=True,
        )
        db.add(superuser)
        await db.commit()
        logger.info(
            "superuser_created",
            email=settings.FIRST_SUPERUSER_EMAIL,
        )
    else:
        logger.info(
            "superuser_exists",
            email=settings.FIRST_SUPERUSER_EMAIL,
        )


async def seed_demo_data(db: AsyncSession) -> None:
    """Seed demo data for development environment.

    Only runs in development mode.

    Args:
        db: Database session.
    """
    if settings.ENVIRONMENT != "development":
        logger.info("skipping_demo_seed", reason="not in development mode")
        return

    logger.info("seeding_demo_data")

    # Add demo users for each role
    demo_users = [
        {
            "email": "patient@demo.com",
            "full_name": "Demo Patient",
            "role": UserRole.PATIENT.value,
        },
        {
            "email": "doctor@demo.com",
            "full_name": "Dr. Demo Doctor",
            "role": UserRole.DOCTOR.value,
        },
        {
            "email": "hotel@demo.com",
            "full_name": "Hotel Manager",
            "role": UserRole.HOTEL_MANAGER.value,
        },
        {
            "email": "restaurant@demo.com",
            "full_name": "Restaurant Manager",
            "role": UserRole.RESTAURANT_MANAGER.value,
        },
    ]

    for user_data in demo_users:
        result = await db.execute(select(User).where(User.email == user_data["email"]))
        existing = result.scalar_one_or_none()

        if existing is None:
            user = User(
                email=user_data["email"],
                hashed_password=get_password_hash("Demo@123456"),
                full_name=user_data["full_name"],
                role=user_data["role"],
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            logger.info("demo_user_created", email=user_data["email"])

    await db.commit()
    logger.info("demo_data_seeded")
