"""Migration script to create doctor profiles for existing doctor users"""
import asyncio
from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.user import User
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.utils.enums import UserRole
from app.core.logging import get_logger

logger = get_logger(__name__)

async def create_missing_profiles():
    """Create doctor/patient profiles for existing users who don't have them"""
    async with async_session_factory() as session:
        try:
            # Find all doctor users without doctor profiles
            result = await session.execute(
                select(User).where(
                    User.role == UserRole.DOCTOR.value,
                    User.is_deleted == False
                )
            )
            doctor_users = result.scalars().all()
            
            doctors_created = 0
            for user in doctor_users:
                # Check if doctor profile already exists
                existing = await session.execute(
                    select(Doctor).where(Doctor.user_id == user.id)
                )
                if existing.scalar_one_or_none() is None:
                    # Create doctor profile
                    doctor = Doctor(
                        user_id=user.id,
                        license_number=None,
                        created_by=user.id,
                    )
                    session.add(doctor)
                    doctors_created += 1
                    logger.info(f"Created doctor profile for user {user.email}")
            
            # Find all patient users without patient profiles
            result = await session.execute(
                select(User).where(
                    User.role == UserRole.PATIENT.value,
                    User.is_deleted == False
                )
            )
            patient_users = result.scalars().all()
            
            patients_created = 0
            for user in patient_users:
                # Check if patient profile already exists
                existing = await session.execute(
                    select(Patient).where(Patient.user_id == user.id)
                )
                if existing.scalar_one_or_none() is None:
                    # Create patient profile
                    patient = Patient(
                        user_id=user.id,
                        created_by=user.id,
                    )
                    session.add(patient)
                    patients_created += 1
                    logger.info(f"Created patient profile for user {user.email}")
            
            await session.commit()
            
            print(f"Migration completed successfully!")
            print(f"- Created {doctors_created} doctor profiles")
            print(f"- Created {patients_created} patient profiles")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    print("Starting migration to create missing doctor/patient profiles...")
    asyncio.run(create_missing_profiles())
