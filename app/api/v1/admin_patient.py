"""Admin patient management endpoints.

Provides admin visibility into:
- patient totals / KPIs
- patient list + detail
- medical records
- consultation history with doctors (end-to-end track)
- bookings and medical reports
"""

from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import joinedload

from app.api.deps import DatabaseSession, RequireAdmin
from app.models.booking import Booking
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.medical_record import Allergy, MedicalCondition, Medication
from app.models.medical_report import MedicalReport
from app.models.patient import Patient
from app.models.user import User
from app.schemas.common import PaginatedResponse

router = APIRouter()


# ============== RESPONSE SCHEMAS ==============


class AdminPatientListItem(BaseModel):
    id: UUID
    user_id: UUID
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    blood_group: Optional[str] = None
    age: Optional[int] = None
    is_active: bool = True
    is_verified: bool = False
    total_consultations: int = 0
    completed_consultations: int = 0
    last_consultation_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminPatientDetail(BaseModel):
    id: UUID
    user_id: UUID
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    date_of_birth: Optional[Any] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry: Optional[Any] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    blood_group: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    age: Optional[int] = None
    bmi: Optional[float] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    current_medications: Optional[str] = None
    medical_history: Optional[dict] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_details: Optional[dict] = None
    preferred_language: Optional[str] = None
    preferences: Optional[dict] = None
    created_at: datetime
    # Stats
    total_consultations: int = 0
    completed_consultations: int = 0
    pending_consultations: int = 0
    cancelled_consultations: int = 0
    total_bookings: int = 0
    total_reports: int = 0
    doctors_consulted: int = 0
    last_consultation_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AdminConsultationItem(BaseModel):
    id: UUID
    reference_number: str
    patient_id: UUID
    patient_name: Optional[str] = None
    doctor_id: UUID
    doctor_name: Optional[str] = None
    doctor_specialty: Optional[str] = None
    hospital_name: Optional[str] = None
    consultation_type: str
    status: str
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: int = 30
    reason: Optional[str] = None
    symptoms: Optional[str] = None
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    notes: Optional[str] = None
    recommendations: Optional[str] = None
    follow_up_required: bool = False
    follow_up_date: Optional[datetime] = None
    fee: float = 0.0
    is_paid: bool = False
    rating: Optional[int] = None
    review: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminConsultationDetail(AdminConsultationItem):
    symptom_duration: Optional[str] = None
    session_id: Optional[str] = None
    recording_url: Optional[str] = None
    doctor_email: Optional[str] = None
    doctor_phone: Optional[str] = None
    patient_email: Optional[str] = None
    patient_phone: Optional[str] = None


class MedicalConditionItem(BaseModel):
    id: UUID
    condition_name: str
    diagnosed_date: Optional[Any] = None
    status: str
    severity: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class AllergyItem(BaseModel):
    id: UUID
    allergen: str
    reaction: Optional[str] = None
    severity: str
    diagnosed_date: Optional[Any] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class MedicationItem(BaseModel):
    id: UUID
    medication_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class AdminPatientRecords(BaseModel):
    patient_id: UUID
    profile_allergies: Optional[str] = None
    profile_chronic_conditions: Optional[str] = None
    profile_current_medications: Optional[str] = None
    profile_medical_history: Optional[dict] = None
    conditions: List[MedicalConditionItem] = []
    allergies: List[AllergyItem] = []
    medications: List[MedicationItem] = []


class AdminReportItem(BaseModel):
    id: UUID
    title: str
    report_type: str
    description: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    doctor_id: Optional[UUID] = None
    doctor_name: Optional[str] = None
    consultation_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminBookingItem(BaseModel):
    id: UUID
    reference_number: str
    booking_type: str
    status: str
    total_price: float
    currency: Optional[str] = None
    is_paid: bool = False
    consultation_id: Optional[UUID] = None
    check_in: Optional[Any] = None
    check_out: Optional[Any] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TimelineEvent(BaseModel):
    event_type: str = Field(..., description="consultation | booking | report | registration")
    event_id: UUID
    title: str
    status: Optional[str] = None
    doctor_id: Optional[UUID] = None
    doctor_name: Optional[str] = None
    occurred_at: datetime
    summary: Optional[str] = None
    metadata: Optional[dict] = None


class AdminPatientTimeline(BaseModel):
    patient_id: UUID
    patient_name: Optional[str] = None
    events: List[TimelineEvent] = []


# ============== HELPERS ==============


async def _get_patient_or_404(db: DatabaseSession, patient_id: UUID) -> Patient:
    result = await db.execute(
        select(Patient)
        .options(joinedload(Patient.user))
        .where(Patient.id == patient_id, Patient.is_deleted == False)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _consultation_to_item(c: Consultation) -> AdminConsultationItem:
    doctor = c.doctor
    patient = c.patient
    return AdminConsultationItem(
        id=c.id,
        reference_number=c.reference_number,
        patient_id=c.patient_id,
        patient_name=patient.user.full_name if patient and patient.user else None,
        doctor_id=c.doctor_id,
        doctor_name=doctor.user.full_name if doctor and doctor.user else None,
        doctor_specialty=doctor.primary_specialty if doctor else None,
        hospital_name=doctor.hospital.name if doctor and doctor.hospital else None,
        consultation_type=c.consultation_type,
        status=c.status,
        scheduled_at=c.scheduled_at,
        started_at=c.started_at,
        ended_at=c.ended_at,
        duration_minutes=c.duration_minutes,
        reason=c.reason,
        symptoms=c.symptoms,
        diagnosis=c.diagnosis,
        prescription=c.prescription,
        notes=c.notes,
        recommendations=c.recommendations,
        follow_up_required=c.follow_up_required,
        follow_up_date=c.follow_up_date,
        fee=c.fee or 0.0,
        is_paid=c.is_paid,
        rating=c.rating,
        review=c.review,
        cancelled_at=c.cancelled_at,
        cancellation_reason=c.cancellation_reason,
        created_at=c.created_at,
    )


async def _patient_stats(db: DatabaseSession, patient_id: UUID) -> dict:
    base = and_(Consultation.patient_id == patient_id, Consultation.is_deleted == False)

    total = (await db.execute(select(func.count()).where(base))).scalar() or 0
    completed = (
        await db.execute(select(func.count()).where(base, Consultation.status == "completed"))
    ).scalar() or 0
    pending = (
        await db.execute(
            select(func.count()).where(
                base,
                Consultation.status.in_(["pending", "scheduled", "waiting", "in_progress"]),
            )
        )
    ).scalar() or 0
    cancelled = (
        await db.execute(select(func.count()).where(base, Consultation.status == "cancelled"))
    ).scalar() or 0
    doctors = (
        await db.execute(select(func.count(func.distinct(Consultation.doctor_id))).where(base))
    ).scalar() or 0
    last = (
        await db.execute(select(func.max(Consultation.scheduled_at)).where(base))
    ).scalar()
    bookings = (
        await db.execute(
            select(func.count()).where(
                Booking.patient_id == patient_id,
                Booking.is_deleted == False,
            )
        )
    ).scalar() or 0
    reports = (
        await db.execute(
            select(func.count()).where(
                MedicalReport.patient_id == patient_id,
                MedicalReport.is_deleted == False,
            )
        )
    ).scalar() or 0

    return {
        "total_consultations": total,
        "completed_consultations": completed,
        "pending_consultations": pending,
        "cancelled_consultations": cancelled,
        "doctors_consulted": doctors,
        "last_consultation_at": last,
        "total_bookings": bookings,
        "total_reports": reports,
    }


# ============== KPIs ==============


@router.get("/total", dependencies=[RequireAdmin])
async def get_total_patients(db: DatabaseSession):
    """Total registered patients."""
    total = (
        await db.execute(select(func.count(Patient.id)).where(Patient.is_deleted == False))
    ).scalar() or 0
    return {"total_patients": total}


@router.get("/active", dependencies=[RequireAdmin])
async def get_active_patients(db: DatabaseSession):
    """Patients whose linked user account is active."""
    total = (
        await db.execute(
            select(func.count(Patient.id))
            .join(User, Patient.user_id == User.id)
            .where(Patient.is_deleted == False, User.is_active == True, User.is_deleted == False)
        )
    ).scalar() or 0
    return {"active_patients": total}


@router.get("/with-consultations", dependencies=[RequireAdmin])
async def get_patients_with_consultations(db: DatabaseSession):
    """Patients who have at least one consultation."""
    total = (
        await db.execute(
            select(func.count(func.distinct(Consultation.patient_id))).where(
                Consultation.is_deleted == False
            )
        )
    ).scalar() or 0
    return {"patients_with_consultations": total}


@router.get("/new", dependencies=[RequireAdmin])
async def get_new_patients(
    db: DatabaseSession,
    days: int = Query(30, ge=1, le=365, description="Look-back window in days"),
):
    """Patients registered in the last N days."""
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(days=days)
    total = (
        await db.execute(
            select(func.count(Patient.id)).where(
                Patient.is_deleted == False,
                Patient.created_at >= since,
            )
        )
    ).scalar() or 0
    return {"new_patients": total, "days": days}


# ============== GLOBAL CONSULTATION TRACK ==============


@router.get(
    "/consultations",
    response_model=PaginatedResponse[AdminConsultationItem],
    dependencies=[RequireAdmin],
)
async def list_all_consultations(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    doctor_id: Optional[UUID] = None,
    patient_id: Optional[UUID] = None,
    search: Optional[str] = None,
):
    """List all consultations across patients (admin track view)."""
    query = (
        select(Consultation)
        .options(
            joinedload(Consultation.patient).joinedload(Patient.user),
            joinedload(Consultation.doctor).joinedload(Doctor.user),
            joinedload(Consultation.doctor).joinedload(Doctor.hospital),
        )
        .where(Consultation.is_deleted == False)
    )

    if status_filter:
        query = query.where(Consultation.status == status_filter)
    if doctor_id:
        query = query.where(Consultation.doctor_id == doctor_id)
    if patient_id:
        query = query.where(Consultation.patient_id == patient_id)
    if search:
        query = (
            query.join(Consultation.patient)
            .join(Patient.user)
            .where(
                or_(
                    User.full_name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                    Consultation.reference_number.ilike(f"%{search}%"),
                )
            )
        )

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(Consultation.scheduled_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().unique().all()

    items = [_consultation_to_item(c) for c in rows]
    return PaginatedResponse.create(items, total, page, page_size)


# ============== PATIENT LIST / DETAIL ==============


@router.get(
    "",
    response_model=PaginatedResponse[AdminPatientListItem],
    dependencies=[RequireAdmin],
)
async def list_patients(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    country: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """List all patients with consultation summary stats."""
    query = (
        select(Patient)
        .options(joinedload(Patient.user))
        .where(Patient.is_deleted == False)
    )

    if search or is_active is not None:
        query = query.join(Patient.user)

    if search:
        query = query.where(
            or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.phone.ilike(f"%{search}%"),
            )
        )
    if country:
        query = query.where(Patient.country.ilike(f"%{country}%"))
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(Patient.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    patients = (await db.execute(query)).scalars().unique().all()

    items: List[AdminPatientListItem] = []
    for p in patients:
        stats = await _patient_stats(db, p.id)
        items.append(
            AdminPatientListItem(
                id=p.id,
                user_id=p.user_id,
                full_name=p.user.full_name if p.user else None,
                email=p.user.email if p.user else None,
                phone=p.user.phone if p.user else None,
                gender=p.gender,
                nationality=p.nationality,
                city=p.city,
                country=p.country,
                blood_group=p.blood_group,
                age=p.age,
                is_active=p.user.is_active if p.user else True,
                is_verified=p.user.is_verified if p.user else False,
                total_consultations=stats["total_consultations"],
                completed_consultations=stats["completed_consultations"],
                last_consultation_at=stats["last_consultation_at"],
                created_at=p.created_at,
            )
        )

    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/{patient_id}",
    response_model=AdminPatientDetail,
    dependencies=[RequireAdmin],
)
async def get_patient_detail(patient_id: UUID, db: DatabaseSession):
    """Full patient profile + aggregate consultation/booking stats."""
    patient = await _get_patient_or_404(db, patient_id)
    stats = await _patient_stats(db, patient_id)
    user = patient.user

    return AdminPatientDetail(
        id=patient.id,
        user_id=patient.user_id,
        full_name=user.full_name if user else None,
        email=user.email if user else None,
        phone=user.phone if user else None,
        avatar_url=user.avatar_url if user else None,
        is_active=user.is_active if user else True,
        is_verified=user.is_verified if user else False,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        nationality=patient.nationality,
        passport_number=patient.passport_number,
        passport_expiry=patient.passport_expiry,
        address_line1=patient.address_line1,
        address_line2=patient.address_line2,
        city=patient.city,
        state=patient.state,
        country=patient.country,
        postal_code=patient.postal_code,
        blood_group=patient.blood_group,
        height_cm=patient.height_cm,
        weight_kg=patient.weight_kg,
        age=patient.age,
        bmi=patient.bmi,
        allergies=patient.allergies,
        chronic_conditions=patient.chronic_conditions,
        current_medications=patient.current_medications,
        medical_history=patient.medical_history,
        emergency_contact_name=patient.emergency_contact_name,
        emergency_contact_phone=patient.emergency_contact_phone,
        emergency_contact_relation=patient.emergency_contact_relation,
        insurance_provider=patient.insurance_provider,
        insurance_policy_number=patient.insurance_policy_number,
        insurance_details=patient.insurance_details,
        preferred_language=patient.preferred_language,
        preferences=patient.preferences,
        created_at=patient.created_at,
        **stats,
    )


# ============== CONSULTATIONS / HISTORY / RECORDS ==============


@router.get(
    "/{patient_id}/consultations",
    response_model=PaginatedResponse[AdminConsultationItem],
    dependencies=[RequireAdmin],
)
async def list_patient_consultations(
    patient_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    doctor_id: Optional[UUID] = None,
):
    """Consultation history for a patient with doctor details."""
    await _get_patient_or_404(db, patient_id)

    query = (
        select(Consultation)
        .options(
            joinedload(Consultation.patient).joinedload(Patient.user),
            joinedload(Consultation.doctor).joinedload(Doctor.user),
            joinedload(Consultation.doctor).joinedload(Doctor.hospital),
        )
        .where(
            Consultation.patient_id == patient_id,
            Consultation.is_deleted == False,
        )
    )
    if status_filter:
        query = query.where(Consultation.status == status_filter)
    if doctor_id:
        query = query.where(Consultation.doctor_id == doctor_id)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(Consultation.scheduled_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().unique().all()

    return PaginatedResponse.create(
        [_consultation_to_item(c) for c in rows],
        total,
        page,
        page_size,
    )


@router.get(
    "/{patient_id}/consultations/{consultation_id}",
    response_model=AdminConsultationDetail,
    dependencies=[RequireAdmin],
)
async def get_patient_consultation_detail(
    patient_id: UUID,
    consultation_id: UUID,
    db: DatabaseSession,
):
    """Single consultation end-to-end detail (patient ↔ doctor)."""
    await _get_patient_or_404(db, patient_id)

    result = await db.execute(
        select(Consultation)
        .options(
            joinedload(Consultation.patient).joinedload(Patient.user),
            joinedload(Consultation.doctor).joinedload(Doctor.user),
            joinedload(Consultation.doctor).joinedload(Doctor.hospital),
        )
        .where(
            Consultation.id == consultation_id,
            Consultation.patient_id == patient_id,
            Consultation.is_deleted == False,
        )
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Consultation not found")

    item = _consultation_to_item(c)
    return AdminConsultationDetail(
        **item.model_dump(),
        symptom_duration=c.symptom_duration,
        session_id=c.session_id,
        recording_url=c.recording_url,
        doctor_email=c.doctor.user.email if c.doctor and c.doctor.user else None,
        doctor_phone=c.doctor.user.phone if c.doctor and c.doctor.user else None,
        patient_email=c.patient.user.email if c.patient and c.patient.user else None,
        patient_phone=c.patient.user.phone if c.patient and c.patient.user else None,
    )


@router.get(
    "/{patient_id}/history",
    response_model=list[AdminConsultationItem],
    dependencies=[RequireAdmin],
)
async def get_patient_consultation_history(
    patient_id: UUID,
    db: DatabaseSession,
    limit: int = Query(50, ge=1, le=200),
):
    """Ordered consultation history with doctors (patient care track)."""
    await _get_patient_or_404(db, patient_id)

    result = await db.execute(
        select(Consultation)
        .options(
            joinedload(Consultation.patient).joinedload(Patient.user),
            joinedload(Consultation.doctor).joinedload(Doctor.user),
            joinedload(Consultation.doctor).joinedload(Doctor.hospital),
        )
        .where(
            Consultation.patient_id == patient_id,
            Consultation.is_deleted == False,
        )
        .order_by(Consultation.scheduled_at.desc())
        .limit(limit)
    )
    rows = result.scalars().unique().all()
    return [_consultation_to_item(c) for c in rows]


@router.get(
    "/{patient_id}/records",
    response_model=AdminPatientRecords,
    dependencies=[RequireAdmin],
)
async def get_patient_medical_records(patient_id: UUID, db: DatabaseSession):
    """Medical records: profile fields + conditions / allergies / medications."""
    patient = await _get_patient_or_404(db, patient_id)

    conditions = (
        await db.execute(
            select(MedicalCondition).where(
                MedicalCondition.patient_id == patient_id,
                MedicalCondition.is_deleted == False,
            )
        )
    ).scalars().all()

    allergies = (
        await db.execute(
            select(Allergy).where(
                Allergy.patient_id == patient_id,
                Allergy.is_deleted == False,
            )
        )
    ).scalars().all()

    medications = (
        await db.execute(
            select(Medication).where(
                Medication.patient_id == patient_id,
                Medication.is_deleted == False,
            )
        )
    ).scalars().all()

    return AdminPatientRecords(
        patient_id=patient_id,
        profile_allergies=patient.allergies,
        profile_chronic_conditions=patient.chronic_conditions,
        profile_current_medications=patient.current_medications,
        profile_medical_history=patient.medical_history,
        conditions=[MedicalConditionItem.model_validate(c) for c in conditions],
        allergies=[AllergyItem.model_validate(a) for a in allergies],
        medications=[MedicationItem.model_validate(m) for m in medications],
    )


@router.get(
    "/{patient_id}/reports",
    response_model=list[AdminReportItem],
    dependencies=[RequireAdmin],
)
async def get_patient_reports(patient_id: UUID, db: DatabaseSession):
    """Medical reports / documents for a patient."""
    await _get_patient_or_404(db, patient_id)

    result = await db.execute(
        select(MedicalReport)
        .where(
            MedicalReport.patient_id == patient_id,
            MedicalReport.is_deleted == False,
        )
        .order_by(MedicalReport.created_at.desc())
    )
    reports = result.scalars().all()

    doctor_ids = {r.doctor_id for r in reports if r.doctor_id}
    doctor_names: dict[UUID, str] = {}
    if doctor_ids:
        doc_rows = (
            await db.execute(
                select(Doctor)
                .options(joinedload(Doctor.user))
                .where(Doctor.id.in_(doctor_ids))
            )
        ).scalars().unique().all()
        for d in doc_rows:
            if d.user:
                doctor_names[d.id] = d.user.full_name

    return [
        AdminReportItem(
            id=r.id,
            title=r.title,
            report_type=r.report_type,
            description=r.description,
            file_url=r.file_url,
            file_name=r.file_name,
            doctor_id=r.doctor_id,
            doctor_name=doctor_names.get(r.doctor_id) if r.doctor_id else None,
            consultation_id=r.consultation_id,
            created_at=r.created_at,
        )
        for r in reports
    ]


@router.get(
    "/{patient_id}/bookings",
    response_model=list[AdminBookingItem],
    dependencies=[RequireAdmin],
)
async def get_patient_bookings(patient_id: UUID, db: DatabaseSession):
    """Booking history for a patient (hotel/apartment/consultation/etc)."""
    await _get_patient_or_404(db, patient_id)

    result = await db.execute(
        select(Booking)
        .where(Booking.patient_id == patient_id, Booking.is_deleted == False)
        .order_by(Booking.created_at.desc())
    )
    bookings = result.scalars().all()

    items = []
    for b in bookings:
        items.append(
            AdminBookingItem(
                id=b.id,
                reference_number=b.reference_number,
                booking_type=b.booking_type,
                status=b.status,
                total_price=b.total_price,
                currency=b.currency,
                is_paid=b.is_paid,
                consultation_id=b.consultation_id,
                check_in=b.check_in_date,
                check_out=b.check_out_date,
                created_at=b.created_at,
            )
        )
    return items


@router.get(
    "/{patient_id}/timeline",
    response_model=AdminPatientTimeline,
    dependencies=[RequireAdmin],
)
async def get_patient_timeline(patient_id: UUID, db: DatabaseSession):
    """
    End-to-end patient care track:
    registration → consultations with doctors → reports → bookings.
    """
    patient = await _get_patient_or_404(db, patient_id)
    events: List[TimelineEvent] = []

    events.append(
        TimelineEvent(
            event_type="registration",
            event_id=patient.id,
            title="Patient registered",
            status="registered",
            occurred_at=patient.created_at,
            summary=patient.user.full_name if patient.user else None,
        )
    )

    consultations = (
        await db.execute(
            select(Consultation)
            .options(
                joinedload(Consultation.doctor).joinedload(Doctor.user),
            )
            .where(
                Consultation.patient_id == patient_id,
                Consultation.is_deleted == False,
            )
            .order_by(Consultation.scheduled_at.desc())
        )
    ).scalars().unique().all()

    for c in consultations:
        doctor_name = c.doctor.user.full_name if c.doctor and c.doctor.user else None
        events.append(
            TimelineEvent(
                event_type="consultation",
                event_id=c.id,
                title=f"Consultation with {doctor_name or 'doctor'}",
                status=c.status,
                doctor_id=c.doctor_id,
                doctor_name=doctor_name,
                occurred_at=c.scheduled_at,
                summary=c.diagnosis or c.reason,
                metadata={
                    "reference_number": c.reference_number,
                    "consultation_type": c.consultation_type,
                    "fee": c.fee,
                    "is_paid": c.is_paid,
                },
            )
        )

    reports = (
        await db.execute(
            select(MedicalReport).where(
                MedicalReport.patient_id == patient_id,
                MedicalReport.is_deleted == False,
            )
        )
    ).scalars().all()

    doctor_ids = {r.doctor_id for r in reports if r.doctor_id}
    doctor_names: dict[UUID, str] = {}
    if doctor_ids:
        doc_rows = (
            await db.execute(
                select(Doctor)
                .options(joinedload(Doctor.user))
                .where(Doctor.id.in_(doctor_ids))
            )
        ).scalars().unique().all()
        for d in doc_rows:
            if d.user:
                doctor_names[d.id] = d.user.full_name

    for r in reports:
        events.append(
            TimelineEvent(
                event_type="report",
                event_id=r.id,
                title=r.title,
                status=r.report_type,
                doctor_id=r.doctor_id,
                doctor_name=doctor_names.get(r.doctor_id) if r.doctor_id else None,
                occurred_at=r.created_at,
                summary=r.description,
                metadata={
                    "file_url": r.file_url,
                    "consultation_id": str(r.consultation_id) if r.consultation_id else None,
                },
            )
        )

    bookings = (
        await db.execute(
            select(Booking).where(
                Booking.patient_id == patient_id,
                Booking.is_deleted == False,
            )
        )
    ).scalars().all()

    for b in bookings:
        events.append(
            TimelineEvent(
                event_type="booking",
                event_id=b.id,
                title=f"{b.booking_type.title()} booking",
                status=b.status,
                occurred_at=b.created_at,
                summary=b.reference_number,
                metadata={
                    "total_price": b.total_price,
                    "is_paid": b.is_paid,
                    "consultation_id": str(b.consultation_id) if b.consultation_id else None,
                },
            )
        )

    events.sort(key=lambda e: e.occurred_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    return AdminPatientTimeline(
        patient_id=patient.id,
        patient_name=patient.user.full_name if patient.user else None,
        events=events,
    )
