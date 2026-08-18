"""Consultation service."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.booking import Booking
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationDoctorUpdate,
    ConsultationListResponse,
    ConsultationResponse,
)
from app.schemas.common import PaginationParams
from app.services.booking_service import BookingService
from app.services.doctor_service import DoctorService
from app.utils.enums import BookingStatus, BookingType, ConsultationStatus
from app.utils.helpers import generate_reference_id
from app.utils.pricing import price_with_platform_fee
from app.utils.notifications import notify

logger = get_logger(__name__)


class ConsultationService:
    """Service for consultation operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, consultation_id: UUID) -> Optional[Consultation]:
        """Get consultation by ID."""
        from sqlalchemy.orm import selectinload
        from app.models.doctor import Doctor
        from app.models.patient import Patient
        from app.models.user import User

        result = await self.db.execute(
            select(Consultation)
            .options(
                selectinload(Consultation.doctor).selectinload(Doctor.user),
                selectinload(Consultation.doctor).selectinload(Doctor.hospital),
                selectinload(Consultation.patient).selectinload(Patient.user),
            )
            .where(Consultation.id == consultation_id)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        pagination: PaginationParams,
        patient_id: Optional[UUID] = None,
        doctor_id: Optional[UUID] = None,
    ) -> tuple[List[Consultation], int]:
        """Get paginated list of consultations."""
        from sqlalchemy.orm import selectinload

        filters = []
        if patient_id:
            filters.append(Consultation.patient_id == patient_id)
        if doctor_id:
            filters.append(Consultation.doctor_id == doctor_id)

        # Get count
        count_query = select(func.count()).select_from(
            select(Consultation.id).where(*filters).subquery()
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Fetch with eager loading
        query = (
            select(Consultation)
            .options(
                selectinload(Consultation.doctor).selectinload(Doctor.user),
                selectinload(Consultation.doctor).selectinload(Doctor.hospital),
                selectinload(Consultation.patient).selectinload(Patient.user),
            )
            .where(*filters)
            .order_by(Consultation.scheduled_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )

        result = await self.db.execute(query)
        consultations = result.scalars().all()

        return list(consultations), total

    # ── Admin-wide views ──────────────────────────────────────
    # get_list above requires a patient or doctor to scope to. These span the
    # whole platform and are only reachable from the admin router.

    async def get_admin_list(
        self,
        pagination: PaginationParams,
        status: Optional[str] = None,
        consultation_type: Optional[str] = None,
        doctor_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None,
        hospital_id: Optional[UUID] = None,
        is_paid: Optional[bool] = None,
        search: Optional[str] = None,
        from_date=None,
        to_date=None,
        today_only: bool = False,
        active_only: bool = False,
        unconfirmed_only: bool = False,
    ) -> tuple[List[Consultation], int]:
        """List consultations across every doctor and patient."""
        from datetime import datetime as _dt, time as _time, timedelta, timezone as _tz

        from sqlalchemy import or_
        from sqlalchemy.orm import selectinload

        from app.models.user import User

        filters = [Consultation.is_deleted == False]
        if status:
            filters.append(Consultation.status == status)
        if consultation_type:
            filters.append(Consultation.consultation_type == consultation_type)
        if doctor_id:
            filters.append(Consultation.doctor_id == doctor_id)
        if patient_id:
            filters.append(Consultation.patient_id == patient_id)
        if is_paid is not None:
            filters.append(Consultation.is_paid == is_paid)
        if active_only:
            filters.append(
                Consultation.status.in_([
                    ConsultationStatus.WAITING.value,
                    ConsultationStatus.IN_PROGRESS.value,
                ])
            )
        if unconfirmed_only:
            filters.append(Consultation.status == ConsultationStatus.PENDING.value)
        if today_only:
            now = _dt.now(_tz.utc)
            start = _dt.combine(now.date(), _time.min, tzinfo=_tz.utc)
            filters.append(Consultation.scheduled_at >= start)
            filters.append(Consultation.scheduled_at < start + timedelta(days=1))
        if from_date:
            filters.append(
                Consultation.scheduled_at
                >= _dt(from_date.year, from_date.month, from_date.day, tzinfo=_tz.utc)
            )
        if to_date:
            filters.append(
                Consultation.scheduled_at
                < _dt(to_date.year, to_date.month, to_date.day, tzinfo=_tz.utc) + timedelta(days=1)
            )
        if hospital_id:
            filters.append(
                Consultation.doctor_id.in_(
                    select(Doctor.id).where(Doctor.hospital_id == hospital_id)
                )
            )
        if search:
            like = f"%{search}%"
            doctor_user_ids = select(Doctor.id).join(User, Doctor.user_id == User.id).where(
                or_(User.full_name.ilike(like), User.email.ilike(like))
            )
            patient_user_ids = select(Patient.id).join(User, Patient.user_id == User.id).where(
                or_(User.full_name.ilike(like), User.email.ilike(like))
            )
            filters.append(
                or_(
                    Consultation.reference_number.ilike(like),
                    Consultation.doctor_id.in_(doctor_user_ids),
                    Consultation.patient_id.in_(patient_user_ids),
                )
            )

        total = (
            await self.db.execute(
                select(func.count()).select_from(
                    select(Consultation.id).where(*filters).subquery()
                )
            )
        ).scalar() or 0

        result = await self.db.execute(
            select(Consultation)
            .options(
                selectinload(Consultation.doctor).selectinload(Doctor.user),
                selectinload(Consultation.doctor).selectinload(Doctor.hospital),
                selectinload(Consultation.patient).selectinload(Patient.user),
            )
            .where(*filters)
            .order_by(Consultation.scheduled_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
        return list(result.scalars().all()), total

    async def get_admin_stats(self) -> dict:
        """Consultation counts by status and type, plus today's load."""
        from datetime import datetime as _dt, time as _time, timedelta, timezone as _tz

        base = [Consultation.is_deleted == False]

        by_status = dict(
            (
                await self.db.execute(
                    select(Consultation.status, func.count(Consultation.id))
                    .where(*base)
                    .group_by(Consultation.status)
                )
            ).all()
        )
        by_type = dict(
            (
                await self.db.execute(
                    select(Consultation.consultation_type, func.count(Consultation.id))
                    .where(*base)
                    .group_by(Consultation.consultation_type)
                )
            ).all()
        )

        now = _dt.now(_tz.utc)
        day_start = _dt.combine(now.date(), _time.min, tzinfo=_tz.utc)
        today = (
            await self.db.execute(
                select(func.count(Consultation.id)).where(
                    *base,
                    Consultation.scheduled_at >= day_start,
                    Consultation.scheduled_at < day_start + timedelta(days=1),
                )
            )
        ).scalar() or 0

        overdue_pending = (
            await self.db.execute(
                select(func.count(Consultation.id)).where(
                    *base,
                    Consultation.status == ConsultationStatus.PENDING.value,
                    Consultation.scheduled_at < now,
                )
            )
        ).scalar() or 0

        unpaid = (
            await self.db.execute(
                select(func.count(Consultation.id)).where(*base, Consultation.is_paid == False)
            )
        ).scalar() or 0

        total = sum(by_status.values())
        completed = by_status.get(ConsultationStatus.COMPLETED.value, 0)
        cancelled = by_status.get(ConsultationStatus.CANCELLED.value, 0)
        missed = by_status.get(ConsultationStatus.MISSED.value, 0)

        return {
            "total": total,
            "today": today,
            "pending": by_status.get(ConsultationStatus.PENDING.value, 0),
            "scheduled": by_status.get(ConsultationStatus.SCHEDULED.value, 0),
            "in_progress": by_status.get(ConsultationStatus.IN_PROGRESS.value, 0)
            + by_status.get(ConsultationStatus.WAITING.value, 0),
            "completed": completed,
            "cancelled": cancelled,
            "missed": missed,
            "unpaid": unpaid,
            "overdue_pending": overdue_pending,
            "completion_rate": round(completed / total * 100, 2) if total else 0.0,
            "cancellation_rate": round(cancelled / total * 100, 2) if total else 0.0,
            "no_show_rate": round(missed / total * 100, 2) if total else 0.0,
            "by_status": by_status,
            "by_type": by_type,
        }

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

        # Free consultations attract no platform fee.
        _, consultation_platform_fee, consultation_total = price_with_platform_fee(
            consultation.fee
        )

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
            platform_fee=consultation_platform_fee,
            total_price=consultation_total,
            created_by=created_by,
        )
        self.db.add(booking)

        await self.db.commit()
        await self.db.refresh(consultation)

        logger.info("consultation_created", consultation_id=str(consultation.id))

        from app.utils.admin_notify import notify_admin_new_consultation

        await notify_admin_new_consultation(self.db, consultation)
        await self.db.commit()

        return await self.get_by_id(consultation.id)

    # ------------------------------------------------------------------
    # Join consultation (return session/meet details)
    # ------------------------------------------------------------------

    async def join_consultation(
        self, consultation_id: UUID, user_id: UUID
    ) -> dict:
        """Return session details (meet link, status) for joining a consultation."""
        result = await self.db.execute(
            select(Consultation).where(
                Consultation.id == consultation_id,
                Consultation.is_deleted == False,
            )
        )
        consultation = result.scalar_one_or_none()
        if not consultation:
            raise ValueError("Consultation not found")

        if consultation.status == ConsultationStatus.CANCELLED.value:
            raise ValueError("Cannot join a cancelled consultation")

        if consultation.status == ConsultationStatus.COMPLETED.value:
            raise ValueError("This consultation has already been completed")

        session_data = consultation.session_data if isinstance(consultation.session_data, dict) else {}
        meet_link = session_data.get("meet_link")
        platform = session_data.get("platform")

        if platform in ("jaas", "daily", "jitsi_selfhosted") and session_data.get("room"):
            user_result = await self.db.execute(select(User).where(User.id == user_id))
            joining_user = user_result.scalar_one_or_none()
            joining_name = joining_user.full_name if joining_user else "Guest"

            # Both patient and doctor join as moderator/owner — neither
            # should see a "waiting for the host" screen.
            if platform == "jaas":
                from app.utils.google_meet import generate_jaas_join_link

                meet_link = generate_jaas_join_link(
                    room=session_data["room"],
                    user_id=str(user_id),
                    name=joining_name,
                    email=joining_user.email if joining_user else "",
                )
            elif platform == "jitsi_selfhosted":
                from app.utils.google_meet import generate_selfhosted_jitsi_join_link

                meet_link = generate_selfhosted_jitsi_join_link(
                    room=session_data["room"],
                    user_id=str(user_id),
                    name=joining_name,
                    email=joining_user.email if joining_user else "",
                )
            else:
                from app.utils.daily_co import generate_daily_join_link

                meet_link = await generate_daily_join_link(
                    room=session_data["room"],
                    name=joining_name,
                )

            if not meet_link:
                raise ValueError("Video call is temporarily unavailable. Please try again shortly.")

        return {
            "consultation_id": consultation.id,
            "reference_number": consultation.reference_number,
            "status": consultation.status,
            "meet_link": meet_link,
            "session_id": consultation.session_id,
            "platform": platform,
            "scheduled_at": consultation.scheduled_at,
            "duration_minutes": consultation.duration_minutes,
        }

    # ------------------------------------------------------------------
    # Start consultation
    # ------------------------------------------------------------------

    async def start_consultation(
        self, consultation_id: UUID, started_by: UUID
    ) -> Consultation:
        """Transition consultation from SCHEDULED/WAITING → IN_PROGRESS."""
        result = await self.db.execute(
            select(Consultation).where(
                Consultation.id == consultation_id,
                Consultation.is_deleted == False,
            )
        )
        consultation = result.scalar_one_or_none()
        if not consultation:
            raise ValueError("Consultation not found")

        if consultation.status in {
            ConsultationStatus.COMPLETED.value,
            ConsultationStatus.CANCELLED.value,
        }:
            raise ValueError(f"Cannot start a {consultation.status} consultation")

        if consultation.status == ConsultationStatus.IN_PROGRESS.value:
            raise ValueError("Consultation is already in progress")

        consultation.status = ConsultationStatus.IN_PROGRESS.value
        consultation.started_at = datetime.now(timezone.utc)
        consultation.updated_by = started_by

        # Update linked booking status
        booking_result = await self.db.execute(
            select(Booking).where(
                Booking.consultation_id == consultation_id,
                Booking.is_deleted == False,
            )
        )
        booking = booking_result.scalar_one_or_none()
        if booking:
            booking.status = BookingStatus.IN_PROGRESS.value
            booking.updated_by = started_by

        await self.db.commit()
        await self.db.refresh(consultation)
        logger.info("consultation_started", consultation_id=str(consultation_id))

        # Notify patient that consultation has started
        try:
            patient_result = await self.db.execute(
                select(Patient).where(Patient.id == consultation.patient_id)
            )
            patient_rec = patient_result.scalar_one_or_none()
            if patient_rec:
                p_user_result = await self.db.execute(
                    select(User).where(User.id == patient_rec.user_id)
                )
                p_user = p_user_result.scalar_one_or_none()
                if p_user:
                    await notify(
                        db=self.db,
                        user_id=p_user.id,
                        title="Consultation Started",
                        message=f"Your consultation {consultation.reference_number} has started. Please join now.",
                        notification_type="consultation",
                        entity_type="consultation",
                        entity_id=consultation.id,
                        action_url=f"/consultation/{consultation.id}/join",
                        created_by=started_by,
                    )
        except Exception as exc:
            logger.error("start_notification_failed", error=str(exc))

        return await self.get_by_id(consultation.id)

    # ------------------------------------------------------------------
    # Confirm appointment (doctor: pending → scheduled)
    # ------------------------------------------------------------------

    async def confirm_appointment(
        self, consultation_id: UUID, confirmed_by: UUID
    ) -> Consultation:
        """Doctor confirms a pending appointment → SCHEDULED."""
        result = await self.db.execute(
            select(Consultation).where(
                Consultation.id == consultation_id,
                Consultation.is_deleted == False,
            )
        )
        consultation = result.scalar_one_or_none()
        if not consultation:
            raise ValueError("Consultation not found")

        if consultation.status != ConsultationStatus.PENDING.value:
            raise ValueError(
                f"Only pending appointments can be confirmed. Current status: {consultation.status}"
            )

        consultation.status = ConsultationStatus.SCHEDULED.value
        consultation.updated_by = confirmed_by

        # Update linked booking → confirmed
        booking_result = await self.db.execute(
            select(Booking).where(
                Booking.consultation_id == consultation_id,
                Booking.is_deleted == False,
            )
        )
        booking = booking_result.scalar_one_or_none()
        if booking:
            booking.status = BookingStatus.CONFIRMED.value
            booking.confirmed_at = datetime.now(timezone.utc)
            booking.confirmed_by = confirmed_by
            booking.updated_by = confirmed_by

        await self.db.commit()
        await self.db.refresh(consultation)
        logger.info("appointment_confirmed", consultation_id=str(consultation_id))

        # Notify patient
        try:
            patient_result = await self.db.execute(
                select(Patient).where(Patient.id == consultation.patient_id)
            )
            patient_rec = patient_result.scalar_one_or_none()
            if patient_rec:
                p_user_result = await self.db.execute(
                    select(User).where(User.id == patient_rec.user_id)
                )
                p_user = p_user_result.scalar_one_or_none()
                if p_user:
                    await notify(
                        db=self.db,
                        user_id=p_user.id,
                        title="Appointment Confirmed",
                        message=f"Your appointment {consultation.reference_number} has been confirmed by the doctor.",
                        notification_type="consultation",
                        entity_type="consultation",
                        entity_id=consultation.id,
                        action_url=f"/consultation/{consultation.id}",
                        created_by=confirmed_by,
                    )
        except Exception as exc:
            logger.error("confirm_notification_failed", error=str(exc))

        return await self.get_by_id(consultation.id)

    # ------------------------------------------------------------------
    # Reject appointment (doctor: pending → cancelled)
    # ------------------------------------------------------------------

    async def reject_appointment(
        self, consultation_id: UUID, rejected_by: UUID, reason: Optional[str] = None
    ) -> Consultation:
        """Doctor rejects a pending appointment → CANCELLED."""
        result = await self.db.execute(
            select(Consultation).where(
                Consultation.id == consultation_id,
                Consultation.is_deleted == False,
            )
        )
        consultation = result.scalar_one_or_none()
        if not consultation:
            raise ValueError("Consultation not found")

        if consultation.status != ConsultationStatus.PENDING.value:
            raise ValueError(
                f"Only pending appointments can be rejected. Current status: {consultation.status}"
            )

        now = datetime.now(timezone.utc)
        consultation.status = ConsultationStatus.CANCELLED.value
        consultation.cancelled_at = now
        consultation.cancelled_by = rejected_by
        consultation.cancellation_reason = reason or "Rejected by doctor"
        consultation.updated_by = rejected_by

        # Cancel linked booking
        booking_result = await self.db.execute(
            select(Booking).where(
                Booking.consultation_id == consultation_id,
                Booking.is_deleted == False,
            )
        )
        booking = booking_result.scalar_one_or_none()
        if booking:
            booking.status = BookingStatus.CANCELLED.value
            booking.cancelled_at = now
            booking.cancelled_by = rejected_by
            booking.cancellation_reason = reason or "Rejected by doctor"
            booking.updated_by = rejected_by

        await self.db.commit()
        await self.db.refresh(consultation)
        logger.info("appointment_rejected", consultation_id=str(consultation_id))

        # Notify patient
        try:
            patient_result = await self.db.execute(
                select(Patient).where(Patient.id == consultation.patient_id)
            )
            patient_rec = patient_result.scalar_one_or_none()
            if patient_rec:
                p_user_result = await self.db.execute(
                    select(User).where(User.id == patient_rec.user_id)
                )
                p_user = p_user_result.scalar_one_or_none()
                if p_user:
                    await notify(
                        db=self.db,
                        user_id=p_user.id,
                        title="Appointment Rejected",
                        message=f"Your appointment {consultation.reference_number} has been declined by the doctor."
                        + (f" Reason: {reason}" if reason else ""),
                        notification_type="consultation",
                        entity_type="consultation",
                        entity_id=consultation.id,
                        action_url=f"/consultation/{consultation.id}",
                        created_by=rejected_by,
                    )
        except Exception as exc:
            logger.error("reject_notification_failed", error=str(exc))

        return await self.get_by_id(consultation.id)

    # ------------------------------------------------------------------
    # Complete consultation
    # ------------------------------------------------------------------

    async def complete_consultation(
        self,
        consultation_id: UUID,
        completed_by: UUID,
        doctor_notes: Optional[ConsultationDoctorUpdate] = None,
    ) -> Consultation:
        """Transition consultation → COMPLETED and optionally save doctor notes."""
        result = await self.db.execute(
            select(Consultation).where(
                Consultation.id == consultation_id,
                Consultation.is_deleted == False,
            )
        )
        consultation = result.scalar_one_or_none()
        if not consultation:
            raise ValueError("Consultation not found")

        if consultation.status == ConsultationStatus.COMPLETED.value:
            raise ValueError("Consultation is already completed")

        if consultation.status == ConsultationStatus.CANCELLED.value:
            raise ValueError("Cannot complete a cancelled consultation")

        consultation.status = ConsultationStatus.COMPLETED.value
        consultation.ended_at = datetime.now(timezone.utc)
        consultation.updated_by = completed_by

        # If the consultation was never formally started, set started_at too
        if not consultation.started_at:
            consultation.started_at = consultation.scheduled_at

        # Apply doctor notes if provided
        if doctor_notes:
            for field, value in doctor_notes.model_dump(exclude_none=True).items():
                setattr(consultation, field, value)

        # Update linked booking status
        booking_result = await self.db.execute(
            select(Booking).where(
                Booking.consultation_id == consultation_id,
                Booking.is_deleted == False,
            )
        )
        booking = booking_result.scalar_one_or_none()
        if booking:
            booking.status = BookingStatus.COMPLETED.value
            booking.updated_by = completed_by

        await self.db.commit()
        await self.db.refresh(consultation)
        logger.info("consultation_completed", consultation_id=str(consultation_id))

        # Notify patient that consultation is completed
        try:
            patient_result = await self.db.execute(
                select(Patient).where(Patient.id == consultation.patient_id)
            )
            patient_rec = patient_result.scalar_one_or_none()
            if patient_rec:
                p_user_result = await self.db.execute(
                    select(User).where(User.id == patient_rec.user_id)
                )
                p_user = p_user_result.scalar_one_or_none()
                if p_user:
                    await notify(
                        db=self.db,
                        user_id=p_user.id,
                        title="Consultation Completed",
                        message=f"Your consultation {consultation.reference_number} has been completed. You can now view notes and leave a rating.",
                        notification_type="consultation",
                        entity_type="consultation",
                        entity_id=consultation.id,
                        action_url=f"/consultation/{consultation.id}",
                        created_by=completed_by,
                    )
        except Exception as exc:
            logger.error("complete_notification_failed", error=str(exc))

        return await self.get_by_id(consultation.id)

    # ------------------------------------------------------------------
    # Generic status update (doctor)
    # ------------------------------------------------------------------

    ALLOWED_TRANSITIONS: dict[str, set[str]] = {
        ConsultationStatus.PENDING.value: {
            ConsultationStatus.SCHEDULED.value,
            ConsultationStatus.CANCELLED.value,
        },
        ConsultationStatus.SCHEDULED.value: {
            ConsultationStatus.WAITING.value,
            ConsultationStatus.IN_PROGRESS.value,
            ConsultationStatus.COMPLETED.value,
            ConsultationStatus.CANCELLED.value,
            ConsultationStatus.MISSED.value,
        },
        ConsultationStatus.WAITING.value: {
            ConsultationStatus.IN_PROGRESS.value,
            ConsultationStatus.CANCELLED.value,
            ConsultationStatus.MISSED.value,
        },
        ConsultationStatus.IN_PROGRESS.value: {
            ConsultationStatus.COMPLETED.value,
            ConsultationStatus.CANCELLED.value,
        },
    }

    STATUS_TO_BOOKING: dict[str, str] = {
        ConsultationStatus.PENDING.value: BookingStatus.PENDING.value,
        ConsultationStatus.SCHEDULED.value: BookingStatus.CONFIRMED.value,
        ConsultationStatus.WAITING.value: BookingStatus.CONFIRMED.value,
        ConsultationStatus.IN_PROGRESS.value: BookingStatus.IN_PROGRESS.value,
        ConsultationStatus.COMPLETED.value: BookingStatus.COMPLETED.value,
        ConsultationStatus.CANCELLED.value: BookingStatus.CANCELLED.value,
        ConsultationStatus.MISSED.value: BookingStatus.NO_SHOW.value,
    }

    async def update_status(
        self,
        consultation_id: UUID,
        new_status: ConsultationStatus,
        updated_by: UUID,
        notes: Optional[str] = None,
    ) -> Consultation:
        """Generic status transition with validation."""
        result = await self.db.execute(
            select(Consultation).where(
                Consultation.id == consultation_id,
                Consultation.is_deleted == False,
            )
        )
        consultation = result.scalar_one_or_none()
        if not consultation:
            raise ValueError("Consultation not found")

        current = consultation.status
        target = new_status.value

        # Validate transition
        allowed = self.ALLOWED_TRANSITIONS.get(current)
        if allowed is None:
            raise ValueError(f"Cannot change status of a {current} consultation")
        if target not in allowed:
            raise ValueError(
                f"Invalid transition: {current} → {target}. "
                f"Allowed: {', '.join(sorted(allowed))}"
            )

        now = datetime.now(timezone.utc)
        consultation.status = target
        consultation.updated_by = updated_by

        if target == ConsultationStatus.IN_PROGRESS.value and not consultation.started_at:
            consultation.started_at = now
        elif target == ConsultationStatus.COMPLETED.value:
            consultation.ended_at = now
            if not consultation.started_at:
                consultation.started_at = consultation.scheduled_at
        elif target == ConsultationStatus.CANCELLED.value:
            consultation.cancelled_at = now
            consultation.cancelled_by = updated_by
            if notes:
                consultation.cancellation_reason = notes

        if notes and target != ConsultationStatus.CANCELLED.value:
            consultation.notes = notes

        # Sync linked booking
        booking_status = self.STATUS_TO_BOOKING.get(target)
        if booking_status:
            booking_result = await self.db.execute(
                select(Booking).where(
                    Booking.consultation_id == consultation_id,
                    Booking.is_deleted == False,
                )
            )
            booking = booking_result.scalar_one_or_none()
            if booking:
                booking.status = booking_status
                booking.updated_by = updated_by
                if target == ConsultationStatus.CANCELLED.value:
                    booking.cancelled_at = now
                    booking.cancelled_by = updated_by
                    if notes:
                        booking.cancellation_reason = notes
                    # Same policy and queue as any other cancellation — a paid
                    # consultation is owed money like a paid hotel stay.
                    from app.services.booking_service import BookingService

                    BookingService.queue_refund(booking)

        await self.db.commit()
        await self.db.refresh(consultation)
        logger.info("consultation_status_updated", consultation_id=str(consultation_id), old=current, new=target)

        # Notify patient
        try:
            patient_result = await self.db.execute(
                select(Patient).where(Patient.id == consultation.patient_id)
            )
            patient_rec = patient_result.scalar_one_or_none()
            if patient_rec:
                p_user_result = await self.db.execute(
                    select(User).where(User.id == patient_rec.user_id)
                )
                p_user = p_user_result.scalar_one_or_none()
                if p_user:
                    await notify(
                        db=self.db,
                        user_id=p_user.id,
                        title="Consultation Status Updated",
                        message=f"Your consultation {consultation.reference_number} status changed to {target}.",
                        notification_type="consultation",
                        entity_type="consultation",
                        entity_id=consultation.id,
                        action_url=f"/consultation/{consultation.id}",
                        created_by=updated_by,
                    )
        except Exception as exc:
            logger.error("status_update_notification_failed", error=str(exc))

        return await self.get_by_id(consultation.id)

    # ------------------------------------------------------------------
    # Update doctor notes (post-consultation)
    # ------------------------------------------------------------------

    async def update_doctor_notes(
        self,
        consultation_id: UUID,
        doctor_user_id: UUID,
        data: ConsultationDoctorUpdate,
    ) -> Consultation:
        """Update diagnosis, prescription, notes, etc. Only owning doctor allowed."""
        result = await self.db.execute(
            select(Consultation).where(
                Consultation.id == consultation_id,
                Consultation.is_deleted == False,
            )
        )
        consultation = result.scalar_one_or_none()
        if not consultation:
            raise ValueError("Consultation not found")

        # Verify the user is the assigned doctor
        doctor_result = await self.db.execute(
            select(Doctor).where(
                Doctor.id == consultation.doctor_id,
                Doctor.is_deleted == False,
            )
        )
        doctor = doctor_result.scalar_one_or_none()
        if not doctor or doctor.user_id != doctor_user_id:
            raise ValueError("Only the assigned doctor can update consultation notes")

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(consultation, field, value)
        consultation.updated_by = doctor_user_id

        await self.db.commit()
        await self.db.refresh(consultation)
        logger.info("consultation_notes_updated", consultation_id=str(consultation_id))

        # Notify patient that doctor has updated notes
        try:
            patient_result = await self.db.execute(
                select(Patient).where(Patient.id == consultation.patient_id)
            )
            patient_rec = patient_result.scalar_one_or_none()
            if patient_rec:
                p_user_result = await self.db.execute(
                    select(User).where(User.id == patient_rec.user_id)
                )
                p_user = p_user_result.scalar_one_or_none()
                if p_user:
                    await notify(
                        db=self.db,
                        user_id=p_user.id,
                        title="Doctor Notes Updated",
                        message=f"Your doctor has updated notes for consultation {consultation.reference_number}.",
                        notification_type="consultation",
                        entity_type="consultation",
                        entity_id=consultation.id,
                        action_url=f"/consultation/{consultation.id}",
                        created_by=doctor_user_id,
                    )
        except Exception as exc:
            logger.error("notes_notification_failed", error=str(exc))

        return await self.get_by_id(consultation.id)

    # ------------------------------------------------------------------
    # List doctor consultations
    # ------------------------------------------------------------------

    async def list_doctor_consultations(
        self,
        doctor_user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[List[Consultation], int]:
        """Return paginated consultations for a doctor."""
        # Find doctor by user_id
        doctor_result = await self.db.execute(
            select(Doctor).where(
                Doctor.user_id == doctor_user_id,
                Doctor.is_deleted == False,
            )
        )
        doctor = doctor_result.scalar_one_or_none()
        if not doctor:
            raise ValueError("Doctor profile not found")

        from sqlalchemy.orm import selectinload

        base_where = [Consultation.doctor_id == doctor.id, Consultation.is_deleted == False]
        if status:
            base_where.append(Consultation.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(
                select(Consultation.id).where(*base_where).subquery()
            )
        )
        total = count_result.scalar() or 0

        query = (
            select(Consultation)
            .options(
                selectinload(Consultation.doctor).selectinload(Doctor.user),
                selectinload(Consultation.doctor).selectinload(Doctor.hospital),
                selectinload(Consultation.patient).selectinload(Patient.user),
            )
            .where(*base_where)
            .order_by(Consultation.scheduled_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await self.db.execute(query)
        return list(rows.scalars().all()), total

    # ------------------------------------------------------------------
    # Rate consultation
    # ------------------------------------------------------------------

    async def rate_consultation(
        self,
        consultation_id: UUID,
        patient_user_id: UUID,
        rating: int,
        review: Optional[str] = None,
    ) -> Consultation:
        """Rate a completed consultation."""
        result = await self.db.execute(
            select(Consultation).where(
                Consultation.id == consultation_id,
                Consultation.is_deleted == False,
            )
        )
        consultation = result.scalar_one_or_none()
        if not consultation:
            raise ValueError("Consultation not found")

        if consultation.status != ConsultationStatus.COMPLETED.value:
            raise ValueError("Can only rate completed consultations")

        if consultation.rating is not None:
            raise ValueError("This consultation has already been rated")

        consultation.rating = rating
        consultation.review = review
        consultation.updated_by = patient_user_id

        await self.db.commit()
        await self.db.refresh(consultation)
        logger.info("consultation_rated", consultation_id=str(consultation_id), rating=rating)

        # Notify doctor about the rating
        try:
            doctor_result = await self.db.execute(
                select(Doctor).where(
                    Doctor.id == consultation.doctor_id,
                    Doctor.is_deleted == False,
                )
            )
            doctor_rec = doctor_result.scalar_one_or_none()
            if doctor_rec:
                d_user_result = await self.db.execute(
                    select(User).where(User.id == doctor_rec.user_id)
                )
                d_user = d_user_result.scalar_one_or_none()
                if d_user:
                    await notify(
                        db=self.db,
                        user_id=d_user.id,
                        title="Consultation Rated",
                        message=f"A patient rated consultation {consultation.reference_number}: {rating}/5.",
                        notification_type="consultation",
                        entity_type="consultation",
                        entity_id=consultation.id,
                        created_by=patient_user_id,
                    )
        except Exception as exc:
            logger.error("rating_notification_failed", error=str(exc))

        return await self.get_by_id(consultation.id)
