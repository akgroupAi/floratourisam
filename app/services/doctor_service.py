"""Doctor service."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.doctor import Doctor, DoctorAvailability, DoctorSpecialization
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.doctor import (
    DoctorAvailabilityCreate,
    DoctorCreate,
    DoctorSpecializationCreate,
    DoctorUpdate,
)

logger = get_logger(__name__)


class DoctorService:
    """Service for doctor operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, doctor_id: UUID) -> Optional[Doctor]:
        """Get doctor by ID with relations."""
        result = await self.db.execute(
            select(Doctor)
            .options(
                selectinload(Doctor.user),
                selectinload(Doctor.specializations),
                selectinload(Doctor.availability),
                selectinload(Doctor.hospital),
            )
            .where(Doctor.id == doctor_id, Doctor.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: UUID) -> Optional[Doctor]:
        """Get doctor by user ID."""
        result = await self.db.execute(
            select(Doctor)
            .options(
                selectinload(Doctor.user),
                selectinload(Doctor.specializations),
                selectinload(Doctor.availability),
            )
            .where(Doctor.user_id == user_id, Doctor.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        pagination: PaginationParams,
        specialization: Optional[str] = None,
        hospital_id: Optional[UUID] = None,
        is_verified: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> tuple[List[Doctor], int]:
        """Get paginated list of doctors."""
        query = (
            select(Doctor)
            .options(
                selectinload(Doctor.user),
                selectinload(Doctor.specializations),
            )
            .where(Doctor.is_deleted == False)
        )

        # Apply filters
        if hospital_id:
            query = query.where(Doctor.hospital_id == hospital_id)
        if is_verified is not None:
            query = query.where(Doctor.is_verified == is_verified)
        if specialization:
            query = query.join(DoctorSpecialization).where(
                DoctorSpecialization.specialization.ilike(f"%{specialization}%")
            )
        if search:
            query = query.join(User).where(User.full_name.ilike(f"%{search}%"))

        # Get count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting and pagination
        if pagination.sort_by == "rating":
            query = query.order_by(Doctor.rating.desc().nulls_last())
        elif pagination.sort_by == "experience":
            query = query.order_by(Doctor.years_of_experience.desc().nulls_last())
        else:
            query = query.order_by(Doctor.created_at.desc())

        query = query.offset(pagination.offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        doctors = result.scalars().unique().all()

        return list(doctors), total

    async def create(
        self,
        user_id: UUID,
        data: DoctorCreate,
        created_by: Optional[UUID] = None,
    ) -> Doctor:
        """Create doctor profile."""
        doctor = Doctor(
            user_id=user_id,
            hospital_id=data.hospital_id,
            title=data.title,
            license_number=data.license_number,
            license_expiry=data.license_expiry,
            years_of_experience=data.years_of_experience,
            qualifications=data.qualifications,
            bio=data.bio,
            languages_spoken=data.languages_spoken,
            consultation_fee=data.consultation_fee,
            consultation_duration_minutes=data.consultation_duration_minutes,
            video_consultation_enabled=data.video_consultation_enabled,
            chat_consultation_enabled=data.chat_consultation_enabled,
            in_person_enabled=data.in_person_enabled,
            created_by=created_by,
        )

        self.db.add(doctor)
        await self.db.flush()

        # Add specializations
        if data.specializations:
            for spec_data in data.specializations:
                spec = DoctorSpecialization(
                    doctor_id=doctor.id,
                    specialization=spec_data.specialization,
                    is_primary=spec_data.is_primary,
                    certification=spec_data.certification,
                )
                self.db.add(spec)

        await self.db.commit()
        await self.db.refresh(doctor)

        logger.info("doctor_created", doctor_id=str(doctor.id))

        return doctor

    async def update(
        self,
        doctor: Doctor,
        data: DoctorUpdate,
        updated_by: Optional[UUID] = None,
    ) -> Doctor:
        """Update doctor profile."""
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(doctor, field, value)

        doctor.updated_by = updated_by
        doctor.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(doctor)

        logger.info("doctor_updated", doctor_id=str(doctor.id))

        return doctor

    async def add_specialization(
        self,
        doctor: Doctor,
        data: DoctorSpecializationCreate,
    ) -> DoctorSpecialization:
        """Add specialization to doctor."""
        spec = DoctorSpecialization(
            doctor_id=doctor.id,
            specialization=data.specialization,
            is_primary=data.is_primary,
            certification=data.certification,
        )
        self.db.add(spec)
        await self.db.commit()
        await self.db.refresh(spec)

        return spec

    async def set_availability(
        self,
        doctor: Doctor,
        availability_data: List[DoctorAvailabilityCreate],
    ) -> List[DoctorAvailability]:
        """Set doctor availability (replaces existing)."""
        # Remove existing availability
        await self.db.execute(
            DoctorAvailability.__table__.delete().where(
                DoctorAvailability.doctor_id == doctor.id
            )
        )

        # Add new availability
        availability_list = []
        for data in availability_data:
            avail = DoctorAvailability(
                doctor_id=doctor.id,
                day_of_week=data.day_of_week,
                start_time=data.start_time,
                end_time=data.end_time,
                is_available=data.is_available,
                slot_duration_minutes=data.slot_duration_minutes,
                max_appointments=data.max_appointments,
            )
            self.db.add(avail)
            availability_list.append(avail)

        await self.db.commit()

        return availability_list

    async def verify(self, doctor: Doctor, verified_by: UUID) -> Doctor:
        """Verify doctor profile."""
        doctor.is_verified = True
        doctor.verification_date = datetime.now(timezone.utc)
        doctor.updated_by = verified_by
        await self.db.commit()

        logger.info("doctor_verified", doctor_id=str(doctor.id))

        return doctor

    async def delete(self, doctor: Doctor, deleted_by: UUID) -> bool:
        """Soft delete doctor profile."""
        doctor.soft_delete(deleted_by)
        await self.db.commit()

        logger.info("doctor_deleted", doctor_id=str(doctor.id))

        return True
