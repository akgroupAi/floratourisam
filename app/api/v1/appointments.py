"""Appointment scheduling endpoints.

Patient-facing flow:
  1. GET  /appointments/doctors/{doctor_id}/available-slots  — browse open slots
  2. POST /appointments                                       — book an appointment
  3. PUT  /appointments/{appointment_id}/reschedule           — reschedule
  4. GET  /appointments/me                                    — view own appointments
  5. GET  /appointments/{appointment_id}                      — view one appointment
  6. POST /appointments/{appointment_id}/cancel               — cancel an appointment

Doctor schedule management (requires doctor or admin role):
  7. GET  /appointments/schedule/me                           — my availability windows
  8. POST /appointments/schedule                              — add availability window
  9. PUT  /appointments/schedule/{availability_id}            — update window
 10. DELETE /appointments/schedule/{availability_id}          — remove window
"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequireDoctor, RequirePatient
from app.schemas.appointment import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentResponse,
    AppointmentSummary,
    AvailableSlotsResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.appointment_service import AppointmentService
from app.services.patient_service import PatientService
from app.utils.enums import ConsultationType

router = APIRouter()


# ---------------------------------------------------------------------------
# Doctor schedule management schemas (inline)
# ---------------------------------------------------------------------------
from datetime import time as _time
from pydantic import BaseModel, Field
from app.schemas.common import BaseSchema


class DoctorAvailabilityCreate(BaseModel):
    """Define a working window for a day of the week."""
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday … 6=Sunday")
    start_time: _time
    end_time: _time
    is_available: bool = True
    slot_duration_minutes: int = Field(default=30, ge=15, le=120)
    max_appointments: Optional[int] = Field(default=None, ge=1)
    break_start_time: Optional[_time] = None
    break_end_time: Optional[_time] = None


class DoctorAvailabilityUpdate(BaseModel):
    start_time: Optional[_time] = None
    end_time: Optional[_time] = None
    is_available: Optional[bool] = None
    slot_duration_minutes: Optional[int] = Field(default=None, ge=15, le=120)
    max_appointments: Optional[int] = None
    break_start_time: Optional[_time] = None
    break_end_time: Optional[_time] = None


class DoctorAvailabilityResponse(BaseSchema):
    id: UUID
    doctor_id: UUID
    day_of_week: int
    start_time: _time
    end_time: _time
    is_available: bool
    slot_duration_minutes: int
    max_appointments: Optional[int] = None
    break_start_time: Optional[_time] = None
    break_end_time: Optional[_time] = None


class AppointmentRescheduleRequest(BaseModel):
    scheduled_date: date
    scheduled_time: _time
    reason: Optional[str] = Field(default=None, max_length=500)
    # IANA name (e.g. "Asia/Kolkata"). Omit to use the platform default
    # (settings.DEFAULT_TIMEZONE) rather than assuming UTC.
    timezone: Optional[str] = Field(default=None, max_length=50)


# ---------------------------------------------------------------------------
# Slot availability
# ---------------------------------------------------------------------------

@router.get(
    "/doctors/{doctor_id}/available-slots",
    response_model=AvailableSlotsResponse,
    summary="Get available appointment slots",
    description=(
        "Returns all time slots for a doctor on the requested date, in the "
        "doctor's own timezone by default. Pass `timezone` (IANA name, e.g. "
        "\"Asia/Dubai\") to get slots converted for a patient browsing from "
        "elsewhere — the response's `timezone` field says which zone was "
        "used, and each slot carries its own `date` since conversion can "
        "shift it across midnight. Slots already booked (pending / waiting "
        "/ in-progress) are marked `is_available: false` so the frontend "
        "can grey them out. When booking, send back the same `date`/`time`/"
        "`timezone` from the chosen slot as-is."
    ),
)
async def get_available_slots(
    doctor_id: UUID,
    db: DatabaseSession,
    appointment_date: date = Query(..., alias="date", description="Date in YYYY-MM-DD format"),
    consultation_type: Optional[ConsultationType] = Query(
        default=None,
        description="Filter by consultation type (video / in_person).",
    ),
    viewer_timezone: Optional[str] = Query(
        default=None,
        alias="timezone",
        max_length=50,
        description="IANA name to convert slot times into (e.g. \"Asia/Dubai\"). Omit to get slots in the doctor's own timezone.",
    ),
):
    service = AppointmentService(db)
    try:
        return await service.get_available_slots(
            doctor_id=doctor_id,
            requested_date=appointment_date,
            consultation_type=consultation_type,
            viewer_timezone=viewer_timezone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Book appointment
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequirePatient],
    summary="Schedule an appointment",
)
async def schedule_appointment(
    data: AppointmentCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    patient_service = PatientService(db)
    patient = await patient_service.get_or_create(current_user.id)

    service = AppointmentService(db)
    try:
        return await service.schedule_appointment(
            patient=patient,
            data=data,
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Reschedule appointment
# ---------------------------------------------------------------------------

@router.put(
    "/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
    summary="Reschedule an appointment",
    description=(
        "Moves a scheduled appointment to a new date/time. "
        "The new slot must be available (same conflict-check as booking). "
        "A new confirmation email is sent and calendar events are updated."
    ),
)
async def reschedule_appointment(
    appointment_id: UUID,
    body: AppointmentRescheduleRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = AppointmentService(db)
    try:
        return await service.reschedule_appointment(
            consultation_id=appointment_id,
            new_date=body.scheduled_date,
            new_time=body.scheduled_time,
            rescheduled_by=current_user.id,
            reason=body.reason,
            new_timezone=body.timezone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# My appointments
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=PaginatedResponse[AppointmentSummary],
    summary="List my appointments",
)
async def list_my_appointments(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    appointment_status: Optional[str] = Query(default=None, alias="status"),
):
    patient_service = PatientService(db)
    patient = await patient_service.get_by_user_id(current_user.id)
    if not patient:
        return PaginatedResponse.create([], 0, page, page_size)

    service = AppointmentService(db)
    consultations, total = await service.list_patient_appointments(
        patient_id=patient.id,
        page=page,
        page_size=page_size,
        status=appointment_status,
    )

    items = [
        AppointmentSummary(
            id=c.id,
            reference_number=c.reference_number,
            doctor_id=c.doctor_id,
            doctor_name=c.doctor.user.full_name if c.doctor and c.doctor.user else None,
            doctor_specialization=c.doctor.primary_specialty if c.doctor else None,
            consultation_type=c.consultation_type,
            status=c.status,
            scheduled_at=c.scheduled_at,
            duration_minutes=c.duration_minutes,
            fee=c.fee,
            is_paid=c.is_paid,
            meet_link=(c.session_data or {}).get("meet_link") if c.session_data else None,
            created_at=c.created_at,
        )
        for c in consultations
    ]
    return PaginatedResponse.create(items, total, page, page_size)


# ---------------------------------------------------------------------------
# Single appointment
# ---------------------------------------------------------------------------

@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Get appointment details",
)
async def get_appointment(
    appointment_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    from app.services.consultation_service import ConsultationService

    consultation = await ConsultationService(db).get_by_id(appointment_id)
    if not consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    meet_link = (consultation.session_data or {}).get("meet_link") if consultation.session_data else None
    doctor = consultation.doctor
    patient = consultation.patient
    return AppointmentResponse(
        id=consultation.id,
        reference_number=consultation.reference_number,
        patient_id=consultation.patient_id,
        patient_name=patient.user.full_name if patient and patient.user else None,
        patient_email=patient.user.email if patient and patient.user else None,
        doctor_id=consultation.doctor_id,
        doctor_name=doctor.user.full_name if doctor and doctor.user else None,
        doctor_email=doctor.user.email if doctor and doctor.user else None,
        doctor_specialization=doctor.primary_specialty if doctor else None,
        hospital_name=doctor.hospital.name if doctor and doctor.hospital else None,
        consultation_type=consultation.consultation_type,
        status=consultation.status,
        scheduled_at=consultation.scheduled_at,
        duration_minutes=consultation.duration_minutes,
        started_at=consultation.started_at,
        ended_at=consultation.ended_at,
        reason=consultation.reason,
        symptoms=consultation.symptoms,
        symptom_duration=consultation.symptom_duration,
        diagnosis=consultation.diagnosis,
        prescription=consultation.prescription,
        notes=consultation.notes,
        recommendations=consultation.recommendations,
        follow_up_required=consultation.follow_up_required,
        follow_up_date=consultation.follow_up_date,
        meet_link=meet_link,
        session_id=consultation.session_id,
        fee=consultation.fee,
        is_paid=consultation.is_paid,
        payment_id=consultation.payment_id,
        cancelled_at=consultation.cancelled_at,
        cancellation_reason=consultation.cancellation_reason,
        created_at=consultation.created_at,
        updated_at=consultation.updated_at,
    )


# ---------------------------------------------------------------------------
# Cancel appointment
# ---------------------------------------------------------------------------

@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel an appointment",
)
async def cancel_appointment(
    appointment_id: UUID,
    body: AppointmentCancelRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = AppointmentService(db)
    try:
        consultation = await service.cancel_appointment(
            consultation_id=appointment_id,
            reason=body.cancellation_reason,
            cancelled_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    meet_link = (consultation.session_data or {}).get("meet_link") if consultation.session_data else None
    doctor = consultation.doctor
    patient = consultation.patient
    return AppointmentResponse(
        id=consultation.id,
        reference_number=consultation.reference_number,
        patient_id=consultation.patient_id,
        patient_name=patient.user.full_name if patient and patient.user else None,
        patient_email=patient.user.email if patient and patient.user else None,
        doctor_id=consultation.doctor_id,
        doctor_name=doctor.user.full_name if doctor and doctor.user else None,
        doctor_email=doctor.user.email if doctor and doctor.user else None,
        doctor_specialization=doctor.primary_specialty if doctor else None,
        hospital_name=doctor.hospital.name if doctor and doctor.hospital else None,
        consultation_type=consultation.consultation_type,
        status=consultation.status,
        scheduled_at=consultation.scheduled_at,
        duration_minutes=consultation.duration_minutes,
        reason=consultation.reason,
        fee=consultation.fee,
        is_paid=consultation.is_paid,
        follow_up_required=consultation.follow_up_required,
        meet_link=meet_link,
        session_id=consultation.session_id,
        cancelled_at=consultation.cancelled_at,
        cancellation_reason=consultation.cancellation_reason,
        created_at=consultation.created_at,
        updated_at=consultation.updated_at,
    )


# ---------------------------------------------------------------------------
# Doctor schedule management
# ---------------------------------------------------------------------------

@router.get(
    "/schedule/me",
    response_model=List[DoctorAvailabilityResponse],
    dependencies=[RequireDoctor],
    summary="Get my availability schedule",
    description="Returns all availability windows for the authenticated doctor.",
)
async def get_my_schedule(current_user: CurrentUser, db: DatabaseSession):
    service = AppointmentService(db)
    return await service.get_doctor_schedule(current_user.id)


@router.post(
    "/schedule",
    response_model=DoctorAvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireDoctor],
    summary="Add availability window",
    description="Adds a weekly recurring availability slot for the doctor.",
)
async def add_schedule_window(
    data: DoctorAvailabilityCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = AppointmentService(db)
    try:
        return await service.add_availability_window(
            user_id=current_user.id,
            data=data,
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put(
    "/schedule/{availability_id}",
    response_model=DoctorAvailabilityResponse,
    dependencies=[RequireDoctor],
    summary="Update availability window",
)
async def update_schedule_window(
    availability_id: UUID,
    data: DoctorAvailabilityUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = AppointmentService(db)
    try:
        return await service.update_availability_window(
            availability_id=availability_id,
            user_id=current_user.id,
            data=data,
            updated_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete(
    "/schedule/{availability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[RequireDoctor],
    summary="Remove availability window",
)
async def delete_schedule_window(
    availability_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = AppointmentService(db)
    try:
        await service.delete_availability_window(
            availability_id=availability_id,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

