"""Consultation service."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.booking import Booking
from app.models.consultation import Consultation
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationListResponse,
    ConsultationResponse,
)
from app.schemas.common import PaginationParams
from app.services.booking_service import BookingService
from app.services.doctor_service import DoctorService
from app.utils.enums import BookingStatus, BookingType, ConsultationStatus
from app.utils.helpers import generate_reference_id

logger = get_logger(__name__)


class ConsultationService:
    """Service for consultation operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, consultation_id: UUID) -> Optional[Consultation]:
        """Get consultation by ID."""
        result = await self.db.execute(
            select(Consultation).where(Consultation.id == consultation_id)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        pagination: PaginationParams,
        patient_id: Optional[UUID] = None,
        doctor_id: Optional[UUID] = None,
    ) -> tuple[List[Consultation], int]:
        """Get paginated list of consultations."""
        query = select(Consultation)

        if patient_id:
            query = query.where(Consultation.patient_id == patient_id)
        if doctor_id:
            query = query.where(Consultation.doctor_id == doctor_id)

        # Get count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.order_by(Consultation.scheduled_at.desc())
        query = query.offset(pagination.offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        consultations = result.scalars().all()

        return list(consultations), total

    async def create(
        self,
        patient_id: UUID,
        data: ConsultationCreate,
        created_by: Optional[UUID] = None,
    ) -> Consultation:
        """Create a new consultation."""
        # Validate doctor availability (simplified)
        doctor_service = DoctorService(self.db)
        doctor = await doctor_service.get_by_id(data.doctor_id)
        if not doctor:
            raise ValueError("Doctor not found")

        # Create consultation
        consultation = Consultation(
            patient_id=patient_id,
            doctor_id=data.doctor_id,
            consultation_type=data.consultation_type,
            status=ConsultationStatus.SCHEDULED.value,
            scheduled_at=data.scheduled_at,
            reason=data.reason,
            symptoms=data.symptoms,
            symptom_duration=data.symptom_duration,
            fee=doctor.consultation_fee or 0.0,
            reference_number=generate_reference_id("CNS"),
        )
        self.db.add(consultation)
        await self.db.flush()  # Get ID

        # Create associated booking
        booking = Booking(
            patient_id=patient_id,
            booking_type=BookingType.CONSULTATION.value,
            reference_number=generate_reference_id("BKG"),
            consultation_id=consultation.id,
            booking_date=datetime.now(timezone.utc),
            scheduled_time=data.scheduled_at,
            status=BookingStatus.PENDING.value,
            base_price=consultation.fee,
            total_price=consultation.fee,
            created_by=created_by,
        )
        self.db.add(booking)
        
        await self.db.commit()
        await self.db.refresh(consultation)

        logger.info("consultation_created", consultation_id=str(consultation.id))
        return consultation
