"""Appointment scheduling service.

Responsibilities:
- Calculate available time slots for a doctor on a given date
  (respects DoctorAvailability windows, break times, and already-booked consultations)
- Create a full appointment: Consultation + Booking + Calendar Events + emails
- Cancel an appointment
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.models.booking import Booking
from app.models.consultation import Consultation
from app.models.doctor import Doctor, DoctorAvailability
from app.models.patient import Patient
from app.models.system import Event
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentSummary,
    AvailableSlotsResponse,
    TimeSlot,
)
from app.utils.email_sender import (
    render_appointment_confirmation_html,
    render_doctor_appointment_html,
    send_email,
)
from app.utils.enums import BookingStatus, BookingType, ConsultationStatus, ConsultationType
from app.utils.google_meet import add_to_user_calendar, create_meet_event
from app.utils.notifications import notify
from app.utils.helpers import generate_reference_id

logger = get_logger(__name__)

# Statuses that count as "occupying" a slot
_ACTIVE_STATUSES = {
    ConsultationStatus.PENDING.value,
    ConsultationStatus.SCHEDULED.value,
    ConsultationStatus.WAITING.value,
    ConsultationStatus.IN_PROGRESS.value,
}


class AppointmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Slot availability
    # ------------------------------------------------------------------

    async def get_available_slots(
        self,
        doctor_id: UUID,
        requested_date: date,
        consultation_type: Optional[ConsultationType] = None,
    ) -> AvailableSlotsResponse:
        """Return available time slots for a doctor on a given date."""

        # Fetch doctor with availability
        doctor_result = await self.db.execute(
            select(Doctor)
            .options(selectinload(Doctor.availability))
            .where(Doctor.id == doctor_id, Doctor.is_deleted == False)
        )
        doctor = doctor_result.scalar_one_or_none()
        if not doctor:
            raise ValueError("Doctor not found")

        # Validate requested consultation type
        if consultation_type == ConsultationType.VIDEO and not doctor.video_consultation_enabled:
            raise ValueError("This doctor does not offer video consultations")
        if consultation_type == ConsultationType.IN_PERSON and not doctor.in_person_enabled:
            raise ValueError("This doctor does not offer in-person consultations")

        # Find DoctorAvailability for this day of week (0=Monday)
        day_of_week = requested_date.weekday()
        availability = next(
            (a for a in doctor.availability if a.day_of_week == day_of_week and a.is_available),
            None,
        )
        if not availability:
            return AvailableSlotsResponse(
                doctor_id=doctor_id,
                date=requested_date,
                consultation_type=consultation_type.value if consultation_type else None,
                slot_duration_minutes=doctor.consultation_duration_minutes,
                slots=[],
            )

        slot_duration = availability.slot_duration_minutes or doctor.consultation_duration_minutes

        # Generate all theoretical slots for the day
        all_slots = _generate_slots(
            start=availability.start_time,
            end=availability.end_time,
            duration_minutes=slot_duration,
            break_start=availability.break_start_time,
            break_end=availability.break_end_time,
        )

        # Fetch already-booked consultations on this date
        day_start = datetime.combine(requested_date, time.min).replace(tzinfo=timezone.utc)
        day_end = datetime.combine(requested_date, time.max).replace(tzinfo=timezone.utc)

        booked_result = await self.db.execute(
            select(Consultation.scheduled_at, Consultation.duration_minutes).where(
                and_(
                    Consultation.doctor_id == doctor_id,
                    Consultation.scheduled_at >= day_start,
                    Consultation.scheduled_at <= day_end,
                    Consultation.status.in_(_ACTIVE_STATUSES),
                    Consultation.is_deleted == False,
                )
            )
        )
        booked_rows = booked_result.all()

        # Build a set of occupied slot times (accounting for consultation duration)
        occupied: set[time] = set()
        for row in booked_rows:
            booked_start = row.scheduled_at.astimezone(timezone.utc).time().replace(second=0, microsecond=0)
            booked_duration = row.duration_minutes or slot_duration
            booked_start_dt = datetime.combine(requested_date, booked_start)
            booked_end_dt = booked_start_dt + timedelta(minutes=booked_duration)
            for s in all_slots:
                s_start_dt = datetime.combine(requested_date, s)
                s_end_dt = s_start_dt + timedelta(minutes=slot_duration)
                if s_start_dt < booked_end_dt and s_end_dt > booked_start_dt:
                    occupied.add(s)

        # Enforce max_appointments limit
        max_appts = availability.max_appointments
        all_unavailable = max_appts is not None and len(booked_rows) >= max_appts

        slots: List[TimeSlot] = [
            TimeSlot(
                time=slot,
                formatted=_format_time(slot),
                is_available=False if all_unavailable else slot not in occupied,
            )
            for slot in all_slots
        ]

        return AvailableSlotsResponse(
            doctor_id=doctor_id,
            date=requested_date,
            consultation_type=consultation_type.value if consultation_type else None,
            slot_duration_minutes=slot_duration,
            slots=slots,
        )

    # ------------------------------------------------------------------
    # Schedule appointment
    # ------------------------------------------------------------------

    async def schedule_appointment(
        self,
        patient: Patient,
        data: AppointmentCreate,
        created_by: UUID,
    ) -> AppointmentResponse:
        """Full appointment scheduling flow:
        1. Validate slot is still available
        2. Create Consultation + Booking
        3. Generate Google Meet link (if VIDEO)
        4. Create Event records for doctor and patient
        5. Send confirmation emails
        """

        # Validate doctor
        doctor_result = await self.db.execute(
            select(Doctor)
            .options(selectinload(Doctor.availability))
            .where(Doctor.id == data.doctor_id, Doctor.is_deleted == False)
        )
        doctor: Optional[Doctor] = doctor_result.scalar_one_or_none()
        if not doctor:
            raise ValueError("Doctor not found")

        # Validate consultation type availability
        if data.consultation_type == ConsultationType.VIDEO and not doctor.video_consultation_enabled:
            raise ValueError("This doctor does not offer video consultations")
        if data.consultation_type == ConsultationType.IN_PERSON and not doctor.in_person_enabled:
            raise ValueError("This doctor does not offer in-person consultations")

        # Build scheduled_at as timezone-aware UTC datetime
        tz = ZoneInfo(data.timezone) if data.timezone and data.timezone != "UTC" else timezone.utc
        local_dt = datetime.combine(data.scheduled_date, data.scheduled_time).replace(tzinfo=tz)
        scheduled_at = local_dt.astimezone(timezone.utc)

        # Confirm slot is not already taken
        await self._assert_slot_available(doctor.id, scheduled_at, data.duration_minutes)

        # Enforce max_appointments limit for the day
        day_of_week = data.scheduled_date.weekday()
        avail = next(
            (a for a in doctor.availability if a.day_of_week == day_of_week and a.is_available),
            None,
        )
        if avail and avail.max_appointments is not None:
            day_start = datetime.combine(data.scheduled_date, time.min).replace(tzinfo=timezone.utc)
            day_end = datetime.combine(data.scheduled_date, time.max).replace(tzinfo=timezone.utc)
            count_result = await self.db.execute(
                select(func.count()).where(
                    and_(
                        Consultation.doctor_id == doctor.id,
                        Consultation.scheduled_at >= day_start,
                        Consultation.scheduled_at <= day_end,
                        Consultation.status.in_(_ACTIVE_STATUSES),
                        Consultation.is_deleted == False,
                    )
                )
            )
            booked_count = count_result.scalar() or 0
            if booked_count >= avail.max_appointments:
                raise ValueError("Maximum appointments reached for this day")

        # ------------------------------------------------------------------
        # Fetch user records for doctor and patient (needed for email / calendar)
        # ------------------------------------------------------------------
        patient_user_result = await self.db.execute(
            select(User).where(User.id == patient.user_id)
        )
        patient_user: Optional[User] = patient_user_result.scalar_one_or_none()

        doctor_user_result = await self.db.execute(
            select(User).where(User.id == doctor.user_id)
        )
        doctor_user: Optional[User] = doctor_user_result.scalar_one_or_none()

        # ------------------------------------------------------------------
        # Create Consultation
        # ------------------------------------------------------------------
        consultation = Consultation(
            patient_id=patient.id,
            doctor_id=doctor.id,
            consultation_type=data.consultation_type.value,
            status=ConsultationStatus.PENDING.value,
            scheduled_at=scheduled_at,
            duration_minutes=data.duration_minutes,
            reason=data.reason,
            symptoms=data.symptoms,
            symptom_duration=data.symptom_duration,
            fee=doctor.consultation_fee or 0.0,
            reference_number=generate_reference_id("CNS"),
            created_by=created_by,
        )
        self.db.add(consultation)
        await self.db.flush()  # obtain consultation.id

        # ------------------------------------------------------------------
        # Create linked Booking
        # ------------------------------------------------------------------
        booking = Booking(
            patient_id=patient.id,
            booking_type=BookingType.CONSULTATION.value,
            reference_number=generate_reference_id("BKG"),
            consultation_id=consultation.id,
            booking_date=datetime.now(timezone.utc),
            scheduled_time=scheduled_at,
            status=BookingStatus.PENDING.value,
            base_price=consultation.fee,
            total_price=consultation.fee,
            created_by=created_by,
        )
        self.db.add(booking)
        await self.db.flush()

        # ------------------------------------------------------------------
        # Google Meet link (video only)
        # ------------------------------------------------------------------
        meet_link: Optional[str] = None
        google_event_id: Optional[str] = None

        if data.consultation_type == ConsultationType.VIDEO:
            end_dt = scheduled_at + timedelta(minutes=data.duration_minutes)
            attendee_emails = []
            organizer_email = doctor_user.email if doctor_user else settings.EMAIL_FROM_ADDRESS

            if patient_user:
                attendee_emails.append(patient_user.email)

            meet_result = await create_meet_event(
                title=f"Medical Consultation — {consultation.reference_number}",
                description=(
                    f"Patient: {patient_user.full_name if patient_user else 'Patient'}\n"
                    f"Doctor: {doctor_user.full_name if doctor_user else 'Doctor'}\n"
                    f"Reference: {consultation.reference_number}"
                ),
                start_dt=scheduled_at,
                end_dt=end_dt,
                organizer_email=organizer_email,
                attendee_emails=attendee_emails,
                timezone=settings.GOOGLE_CALENDAR_TIMEZONE,
            )
            meet_link = meet_result.get("meet_link")
            google_event_id = meet_result.get("google_event_id")

            # Persist meet link in consultation session data
            consultation.session_id = google_event_id or consultation.reference_number
            consultation.session_data = {
                "meet_link": meet_link,
                "google_event_id": google_event_id,
                "platform": meet_result.get("platform", "google_meet"),
            }

        await self.db.flush()

        # ------------------------------------------------------------------
        # Calendar Events (local DB records for both users)
        # ------------------------------------------------------------------
        end_dt = scheduled_at + timedelta(minutes=data.duration_minutes)
        patient_event_id: Optional[UUID] = None
        doctor_event_id: Optional[UUID] = None

        if patient_user:
            patient_event = Event(
                user_id=patient_user.id,
                title=f"Appointment with {doctor_user.full_name if doctor_user else 'Doctor'}",
                description=data.reason or "Medical consultation",
                event_type="consultation",
                start_time=scheduled_at,
                end_time=end_dt,
                timezone=data.timezone,
                location_type="online" if data.consultation_type == ConsultationType.VIDEO else "in_person",
                meeting_url=meet_link,
                entity_type="consultation",
                entity_id=consultation.id,
                status="confirmed",
                attendees=[
                    {"email": doctor_user.email, "status": "accepted"} if doctor_user else {}
                ],
                reminders=[
                    {"type": "email", "minutes_before": 60},
                    {"type": "popup", "minutes_before": 15},
                ],
                color="#0066cc",
                created_by=created_by,
            )
            self.db.add(patient_event)
            await self.db.flush()
            patient_event_id = patient_event.id

        if doctor_user:
            doctor_event = Event(
                user_id=doctor_user.id,
                title=f"Appointment — {patient_user.full_name if patient_user else 'Patient'} ({consultation.reference_number})",
                description=f"Consultation with patient. Type: {data.consultation_type.value}",
                event_type="consultation",
                start_time=scheduled_at,
                end_time=end_dt,
                timezone=data.timezone,
                location_type="online" if data.consultation_type == ConsultationType.VIDEO else "in_person",
                meeting_url=meet_link,
                entity_type="consultation",
                entity_id=consultation.id,
                status="confirmed",
                attendees=[
                    {"email": patient_user.email, "status": "accepted"} if patient_user else {}
                ],
                reminders=[
                    {"type": "email", "minutes_before": 60},
                    {"type": "popup", "minutes_before": 15},
                ],
                color="#1a7a4c",
                created_by=created_by,
            )
            self.db.add(doctor_event)
            await self.db.flush()
            doctor_event_id = doctor_event.id

        # ------------------------------------------------------------------
        # Persist everything before sending side-effects
        # ------------------------------------------------------------------
        await self.db.commit()
        await self.db.refresh(consultation)

        logger.info(
            "appointment_scheduled",
            consultation_id=str(consultation.id),
            ref=consultation.reference_number,
            type=data.consultation_type.value,
            meet_link=meet_link,
        )

        # ------------------------------------------------------------------
        # Send notifications (best-effort)
        # ------------------------------------------------------------------
        patient_name = patient_user.full_name if patient_user else "Patient"
        doctor_name_tmp = doctor_user.full_name if doctor_user else "Doctor"
        doctor_title_tmp = doctor.title or "Dr."
        doctor_display_tmp = f"{doctor_title_tmp} {doctor_name_tmp}".strip()

        if patient_user:
            try:
                await notify(
                    db=self.db,
                    user_id=patient_user.id,
                    title="Appointment Confirmed",
                    message=f"Your appointment with {doctor_display_tmp} on {data.scheduled_date} is confirmed. Ref: {consultation.reference_number}",
                    notification_type="consultation",
                    entity_type="consultation",
                    entity_id=consultation.id,
                    action_url=f"/consultation/{consultation.id}",
                    created_by=created_by,
                )
            except Exception:
                pass

        if doctor_user:
            try:
                await notify(
                    db=self.db,
                    user_id=doctor_user.id,
                    title="New Appointment",
                    message=f"New appointment from {patient_name} on {data.scheduled_date}. Ref: {consultation.reference_number}",
                    notification_type="consultation",
                    entity_type="consultation",
                    entity_id=consultation.id,
                    action_url=f"/consultation/{consultation.id}",
                    created_by=created_by,
                )
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Send confirmation emails (best-effort — don't fail the request)
        # ------------------------------------------------------------------
        doctor_name = (
            f"{doctor_user.full_name}" if doctor_user else "Doctor"
        )
        doctor_title = doctor.title or "Dr."
        doctor_display = f"{doctor_title} {doctor_name}".strip()

        if patient_user:
            try:
                patient_html = render_appointment_confirmation_html(
                    patient_name=patient_name,
                    doctor_name=doctor_display,
                    consultation_type=data.consultation_type.value,
                    scheduled_at=scheduled_at,
                    duration_minutes=data.duration_minutes,
                    reference_number=consultation.reference_number,
                    meet_link=meet_link,
                    fee=consultation.fee,
                )
                await send_email(
                    db=self.db,
                    to_email=patient_user.email,
                    to_name=patient_name,
                    subject=f"Appointment Confirmed — {consultation.reference_number}",
                    body_html=patient_html,
                    category="consultation",
                    user_id=patient_user.id,
                )
            except Exception as exc:
                logger.error("patient_email_failed", error=str(exc))

        if doctor_user:
            try:
                doctor_html = render_doctor_appointment_html(
                    doctor_name=doctor_display,
                    patient_name=patient_name,
                    consultation_type=data.consultation_type.value,
                    scheduled_at=scheduled_at,
                    duration_minutes=data.duration_minutes,
                    reference_number=consultation.reference_number,
                    meet_link=meet_link,
                    reason=data.reason,
                )
                await send_email(
                    db=self.db,
                    to_email=doctor_user.email,
                    to_name=doctor_display,
                    subject=f"New Appointment — {patient_name} on {data.scheduled_date}",
                    body_html=doctor_html,
                    category="consultation",
                    user_id=doctor_user.id,
                )
            except Exception as exc:
                logger.error("doctor_email_failed", error=str(exc))

        return AppointmentResponse(
            id=consultation.id,
            reference_number=consultation.reference_number,
            booking_reference=booking.reference_number,
            patient_id=patient.id,
            patient_name=patient_name,
            patient_email=patient_user.email if patient_user else None,
            doctor_id=doctor.id,
            doctor_name=doctor_display,
            doctor_email=doctor_user.email if doctor_user else None,
            consultation_type=consultation.consultation_type,
            status=consultation.status,
            scheduled_at=consultation.scheduled_at,
            duration_minutes=consultation.duration_minutes,
            reason=consultation.reason,
            symptoms=consultation.symptoms,
            symptom_duration=consultation.symptom_duration,
            fee=consultation.fee,
            is_paid=consultation.is_paid,
            meet_link=meet_link,
            session_id=consultation.session_id,
            patient_event_id=patient_event_id,
            doctor_event_id=doctor_event_id,
            created_at=consultation.created_at,
            updated_at=consultation.updated_at,
        )

    # ------------------------------------------------------------------
    # Cancel appointment
    # ------------------------------------------------------------------

    async def cancel_appointment(
        self,
        consultation_id: UUID,
        reason: str,
        cancelled_by: UUID,
    ) -> Consultation:
        """Cancel a consultation and its linked booking."""
        result = await self.db.execute(
            select(Consultation)
            .options(
                selectinload(Consultation.doctor).selectinload(Doctor.user),
                selectinload(Consultation.doctor).selectinload(Doctor.hospital),
                selectinload(Consultation.patient).selectinload(Patient.user),
            )
            .where(
                Consultation.id == consultation_id,
                Consultation.is_deleted == False,
            )
        )
        consultation = result.scalar_one_or_none()
        if not consultation:
            raise ValueError("Appointment not found")

        if consultation.status in {
            ConsultationStatus.COMPLETED.value,
            ConsultationStatus.CANCELLED.value,
        }:
            raise ValueError(f"Cannot cancel a {consultation.status} appointment")

        consultation.status = ConsultationStatus.CANCELLED.value
        consultation.cancelled_at = datetime.now(timezone.utc)
        consultation.cancellation_reason = reason
        consultation.cancelled_by = cancelled_by
        consultation.updated_by = cancelled_by

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
            booking.cancelled_at = datetime.now(timezone.utc)
            booking.cancellation_reason = reason
            booking.cancelled_by = cancelled_by

        await self.db.commit()
        await self.db.refresh(consultation)
        logger.info("appointment_cancelled", consultation_id=str(consultation_id))

        # Notify both parties (best-effort)
        try:
            # Resolve patient user
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
                        title="Appointment Cancelled",
                        message=f"Your appointment {consultation.reference_number} has been cancelled.",
                        notification_type="consultation",
                        entity_type="consultation",
                        entity_id=consultation.id,
                        created_by=cancelled_by,
                    )

            # Resolve doctor user
            doctor_result = await self.db.execute(
                select(Doctor).where(Doctor.id == consultation.doctor_id)
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
                        title="Appointment Cancelled",
                        message=f"Appointment {consultation.reference_number} has been cancelled.",
                        notification_type="consultation",
                        entity_type="consultation",
                        entity_id=consultation.id,
                        created_by=cancelled_by,
                    )
        except Exception as exc:
            logger.error("cancel_notification_failed", error=str(exc))

        return consultation

    # ------------------------------------------------------------------
    # List patient appointments
    # ------------------------------------------------------------------

    async def list_patient_appointments(
        self,
        patient_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[List[Consultation], int]:
        """Return paginated consultations for a patient."""
        from sqlalchemy import func
        from sqlalchemy.orm import selectinload

        query = select(Consultation).options(
            selectinload(Consultation.doctor).selectinload(Doctor.user),
            selectinload(Consultation.patient).selectinload(Patient.user),
        ).where(
            Consultation.patient_id == patient_id,
            Consultation.is_deleted == False,
        )
        if status:
            query = query.where(Consultation.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(Consultation.scheduled_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await self.db.execute(query)
        return list(rows.scalars().all()), total

    # ------------------------------------------------------------------
    # Reschedule appointment
    # ------------------------------------------------------------------

    async def reschedule_appointment(
        self,
        consultation_id: UUID,
        new_date: "date",
        new_time: "time",
        rescheduled_by: UUID,
        reason: Optional[str] = None,
    ) -> Consultation:
        """Move a scheduled consultation to a new date/time slot."""
        result = await self.db.execute(
            select(Consultation).where(
                Consultation.id == consultation_id,
                Consultation.is_deleted == False,
            )
        )
        consultation: Optional[Consultation] = result.scalar_one_or_none()
        if not consultation:
            raise ValueError("Appointment not found")

        if consultation.status in {
            ConsultationStatus.COMPLETED.value,
            ConsultationStatus.CANCELLED.value,
        }:
            raise ValueError(f"Cannot reschedule a {consultation.status} appointment")

        # Build new datetime as timezone-aware UTC
        new_dt = datetime.combine(new_date, new_time).replace(tzinfo=timezone.utc)

        # Validate the new slot isn't in the past
        if new_dt < datetime.now(timezone.utc):
            raise ValueError("Cannot reschedule to a past date/time")

        # Check conflicts using actual duration (exclude this consultation itself)
        slot_end = new_dt + timedelta(minutes=consultation.duration_minutes or 30)
        conflict_result = await self.db.execute(
            select(Consultation.scheduled_at, Consultation.duration_minutes).where(
                and_(
                    Consultation.doctor_id == consultation.doctor_id,
                    Consultation.id != consultation_id,
                    Consultation.status.in_(_ACTIVE_STATUSES),
                    Consultation.is_deleted == False,
                    Consultation.scheduled_at < slot_end,
                )
            )
        )
        for row in conflict_result.all():
            existing_end = row.scheduled_at + timedelta(minutes=row.duration_minutes or 30)
            if row.scheduled_at < slot_end and existing_end > new_dt:
                raise ValueError("The new time slot is not available")

        old_scheduled_at = consultation.scheduled_at
        consultation.scheduled_at = new_dt
        consultation.updated_by = rescheduled_by

        # Update linked booking
        booking_result = await self.db.execute(
            select(Booking).where(
                Booking.consultation_id == consultation_id,
                Booking.is_deleted == False,
            )
        )
        booking = booking_result.scalar_one_or_none()
        if booking:
            booking.scheduled_time = new_dt
            booking.updated_by = rescheduled_by

        # Update calendar events
        await self.db.execute(
            select(Event).where(
                Event.entity_type == "consultation",
                Event.entity_id == consultation_id,
                Event.is_deleted == False,
            )
        )

        from sqlalchemy import update as sa_update
        await self.db.execute(
            sa_update(Event)
            .where(
                Event.entity_type == "consultation",
                Event.entity_id == consultation_id,
                Event.is_deleted == False,
            )
            .values(
                start_time=new_dt,
                end_time=slot_end,
                updated_by=rescheduled_by,
            )
        )

        await self.db.commit()
        await self.db.refresh(consultation)

        logger.info(
            "appointment_rescheduled",
            consultation_id=str(consultation_id),
            old=str(old_scheduled_at),
            new=str(new_dt),
        )

        # Notify both parties about reschedule (best-effort)
        try:
            patient_rec_r = await self.db.execute(
                select(Patient).where(Patient.id == consultation.patient_id)
            )
            patient_r = patient_rec_r.scalar_one_or_none()
            if patient_r:
                p_user_r = await self.db.execute(
                    select(User).where(User.id == patient_r.user_id)
                )
                p_usr = p_user_r.scalar_one_or_none()
                if p_usr:
                    await notify(
                        db=self.db,
                        user_id=p_usr.id,
                        title="Appointment Rescheduled",
                        message=f"Your appointment {consultation.reference_number} has been rescheduled to {new_date} at {new_time.strftime('%H:%M')}.",
                        notification_type="consultation",
                        entity_type="consultation",
                        entity_id=consultation.id,
                        created_by=rescheduled_by,
                    )

            doctor_rec_r = await self.db.execute(
                select(Doctor).where(Doctor.id == consultation.doctor_id)
            )
            doc_r = doctor_rec_r.scalar_one_or_none()
            if doc_r:
                d_user_r = await self.db.execute(
                    select(User).where(User.id == doc_r.user_id)
                )
                d_usr = d_user_r.scalar_one_or_none()
                if d_usr:
                    await notify(
                        db=self.db,
                        user_id=d_usr.id,
                        title="Appointment Rescheduled",
                        message=f"Appointment {consultation.reference_number} has been rescheduled to {new_date} at {new_time.strftime('%H:%M')}.",
                        notification_type="consultation",
                        entity_type="consultation",
                        entity_id=consultation.id,
                        created_by=rescheduled_by,
                    )
        except Exception as exc:
            logger.error("reschedule_notification_failed", error=str(exc))

        # Send rescheduled emails (best-effort)
        try:
            patient_user_q = await self.db.execute(
                select(User)
                .join(Patient, Patient.user_id == User.id)
                .where(Patient.id == consultation.patient_id)
            )
        except Exception:
            patient_user_q = None

        try:
            if patient_user_q:
                patient_user = patient_user_q.scalar_one_or_none()
                if patient_user:
                    html = render_appointment_confirmation_html(
                        patient_name=patient_user.full_name or "Patient",
                        doctor_name="Your doctor",
                        consultation_type=consultation.consultation_type,
                        scheduled_at=new_dt,
                        duration_minutes=consultation.duration_minutes or 30,
                        reference_number=consultation.reference_number,
                        meet_link=(consultation.session_data or {}).get("meet_link"),
                        fee=consultation.fee,
                    )
                    await send_email(
                        db=self.db,
                        to_email=patient_user.email,
                        to_name=patient_user.full_name or "Patient",
                        subject=f"Appointment Rescheduled — {consultation.reference_number}",
                        body_html=html,
                        category="consultation",
                        user_id=patient_user.id,
                    )
        except Exception as exc:
            logger.error("reschedule_patient_email_failed", error=str(exc))

        return consultation

    # ------------------------------------------------------------------
    # Doctor schedule (DoctorAvailability) management
    # ------------------------------------------------------------------

    async def get_doctor_schedule(self, user_id: UUID) -> list:
        """Return all DoctorAvailability records for the doctor matching user_id."""
        doctor_result = await self.db.execute(
            select(Doctor).where(
                Doctor.user_id == user_id,
                Doctor.is_deleted == False,
            )
        )
        doctor = doctor_result.scalar_one_or_none()
        if not doctor:
            raise ValueError("Doctor profile not found for this user")

        rows = await self.db.execute(
            select(DoctorAvailability).where(
                DoctorAvailability.doctor_id == doctor.id,
                DoctorAvailability.is_deleted == False,
            ).order_by(DoctorAvailability.day_of_week.asc())
        )
        return list(rows.scalars().all())

    async def add_availability_window(
        self,
        user_id: UUID,
        data: "DoctorAvailabilityCreate",
        created_by: UUID,
    ) -> DoctorAvailability:
        """Add a new weekly availability window for the doctor."""
        doctor_result = await self.db.execute(
            select(Doctor).where(
                Doctor.user_id == user_id,
                Doctor.is_deleted == False,
            )
        )
        doctor = doctor_result.scalar_one_or_none()
        if not doctor:
            raise ValueError("Doctor profile not found")

        if data.end_time <= data.start_time:
            raise ValueError("end_time must be after start_time")

        window = DoctorAvailability(
            doctor_id=doctor.id,
            day_of_week=data.day_of_week,
            start_time=data.start_time,
            end_time=data.end_time,
            is_available=data.is_available,
            slot_duration_minutes=data.slot_duration_minutes,
            max_appointments=data.max_appointments,
            break_start_time=data.break_start_time,
            break_end_time=data.break_end_time,
            created_by=created_by,
        )
        self.db.add(window)
        await self.db.commit()
        await self.db.refresh(window)
        logger.info("doctor_availability_added", doctor_id=str(doctor.id), day=data.day_of_week)
        return window

    async def update_availability_window(
        self,
        availability_id: UUID,
        user_id: UUID,
        data: "DoctorAvailabilityUpdate",
        updated_by: UUID,
    ) -> DoctorAvailability:
        """Update an existing availability window (only the owning doctor can)."""
        result = await self.db.execute(
            select(DoctorAvailability).where(
                DoctorAvailability.id == availability_id,
                DoctorAvailability.is_deleted == False,
            )
        )
        window: Optional[DoctorAvailability] = result.scalar_one_or_none()
        if not window:
            raise ValueError("Availability window not found")

        # Verify ownership
        doctor_result = await self.db.execute(
            select(Doctor).where(Doctor.id == window.doctor_id, Doctor.is_deleted == False)
        )
        doctor = doctor_result.scalar_one_or_none()
        if not doctor or doctor.user_id != user_id:
            raise ValueError("You can only update your own availability windows")

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(window, field, value)
        window.updated_by = updated_by

        await self.db.commit()
        await self.db.refresh(window)
        return window

    async def delete_availability_window(self, availability_id: UUID, user_id: UUID) -> None:
        """Soft-delete an availability window."""
        result = await self.db.execute(
            select(DoctorAvailability).where(
                DoctorAvailability.id == availability_id,
                DoctorAvailability.is_deleted == False,
            )
        )
        window: Optional[DoctorAvailability] = result.scalar_one_or_none()
        if not window:
            raise ValueError("Availability window not found")

        doctor_result = await self.db.execute(
            select(Doctor).where(Doctor.id == window.doctor_id, Doctor.is_deleted == False)
        )
        doctor = doctor_result.scalar_one_or_none()
        if not doctor or doctor.user_id != user_id:
            raise ValueError("You can only delete your own availability windows")

        window.is_deleted = True
        window.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()
        logger.info("doctor_availability_deleted", availability_id=str(availability_id))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _assert_slot_available(
        self, doctor_id: UUID, scheduled_at: datetime, duration_minutes: int
    ) -> None:
        """Raise ValueError if the requested slot overlaps an existing consultation."""
        slot_end = scheduled_at + timedelta(minutes=duration_minutes)
        # Fetch nearby consultations and check overlap using actual duration
        result = await self.db.execute(
            select(Consultation.scheduled_at, Consultation.duration_minutes).where(
                and_(
                    Consultation.doctor_id == doctor_id,
                    Consultation.status.in_(_ACTIVE_STATUSES),
                    Consultation.is_deleted == False,
                    Consultation.scheduled_at < slot_end,
                )
            )
        )
        for row in result.all():
            existing_end = row.scheduled_at + timedelta(minutes=row.duration_minutes or 30)
            if row.scheduled_at < slot_end and existing_end > scheduled_at:
                raise ValueError("The selected time slot is no longer available")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _generate_slots(
    start: time,
    end: time,
    duration_minutes: int,
    break_start: Optional[time] = None,
    break_end: Optional[time] = None,
) -> List[time]:
    """Generate list of slot start times between start and end, excluding breaks."""
    slots: List[time] = []
    base = date.today()
    current = datetime.combine(base, start)
    end_dt = datetime.combine(base, end)
    delta = timedelta(minutes=duration_minutes)

    while current + delta <= end_dt:
        slot_start = current.time()
        slot_end = (current + delta).time()

        # Skip if the slot overlaps the break window
        if break_start and break_end:
            if not (slot_end <= break_start or slot_start >= break_end):
                current += delta
                continue

        slots.append(slot_start)
        current += delta

    return slots


def _format_time(t: time) -> str:
    """Format a time as '10:00 AM'."""
    return datetime.combine(date.today(), t).strftime("%I:%M %p").lstrip("0")
