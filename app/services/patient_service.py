"""Patient service."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.patient import Patient
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.patient import PatientCreate, PatientUpdate

logger = get_logger(__name__)


class PatientService:
    """Service for patient operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, patient_id: UUID) -> Optional[Patient]:
        """Get patient by ID."""
        result = await self.db.execute(
            select(Patient)
            .options(selectinload(Patient.user))
            .where(Patient.id == patient_id, Patient.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: UUID) -> Optional[Patient]:
        """Get patient by user ID."""
        result = await self.db.execute(
            select(Patient)
            .options(selectinload(Patient.user))
            .where(Patient.user_id == user_id, Patient.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        pagination: PaginationParams,
        search: Optional[str] = None,
    ) -> tuple[List[Patient], int]:
        """Get paginated list of patients."""
        query = (
            select(Patient)
            .options(selectinload(Patient.user))
            .where(Patient.is_deleted == False)
        )

        if search:
            # Join with user for search
            query = query.join(User).where(
                (User.full_name.ilike(f"%{search}%"))
                | (User.email.ilike(f"%{search}%"))
            )

        # Get count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.offset(pagination.offset).limit(pagination.page_size)
        query = query.order_by(Patient.created_at.desc())

        result = await self.db.execute(query)
        patients = result.scalars().all()

        return list(patients), total

    async def create(
        self,
        user_id: UUID,
        data: PatientCreate,
        created_by: Optional[UUID] = None,
    ) -> Patient:
        """Create patient profile."""
        patient = Patient(
            user_id=user_id,
            date_of_birth=data.date_of_birth,
            gender=data.gender.value if data.gender else None,
            nationality=data.nationality,
            passport_number=data.passport_number,
            passport_expiry=data.passport_expiry,
            created_by=created_by,
        )

        self.db.add(patient)
        await self.db.commit()
        await self.db.refresh(patient)

        logger.info("patient_created", patient_id=str(patient.id))

        return patient

    async def update(
        self,
        patient: Patient,
        data: PatientUpdate,
        updated_by: Optional[UUID] = None,
    ) -> Patient:
        """Update patient profile."""
        update_data = data.model_dump(exclude_unset=True)

        # Handle enum conversion
        if "gender" in update_data and update_data["gender"]:
            update_data["gender"] = update_data["gender"].value
        if "blood_group" in update_data and update_data["blood_group"]:
            update_data["blood_group"] = update_data["blood_group"].value

        for field, value in update_data.items():
            setattr(patient, field, value)

        patient.updated_by = updated_by
        patient.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(patient)

        logger.info("patient_updated", patient_id=str(patient.id))

        return patient

    async def delete(self, patient: Patient, deleted_by: UUID) -> bool:
        """Soft delete patient profile."""
        patient.soft_delete(deleted_by)
        await self.db.commit()

        logger.info("patient_deleted", patient_id=str(patient.id))

        return True

    async def get_or_create(self, user_id: UUID) -> Patient:
        """Get or create patient profile for user."""
        patient = await self.get_by_user_id(user_id)
        if patient:
            return patient

        patient = Patient(user_id=user_id)
        self.db.add(patient)
        await self.db.commit()
        await self.db.refresh(patient)

        return patient
