"""Patient medical reports endpoints.

Covers all structured report types shown in the patient dashboard:
  - lab_result         → "Lab Results" tab
  - imaging            → X-ray, MRI, CT scan
  - prescription       → Doctor-issued prescriptions
  - medical_certificate → Fit-to-fly / fitness certificates
  - medical_travel     → Travel clearance / insurance letters
  - other              → Miscellaneous clinical documents

Endpoints are mounted under /patients (see api_router.py):
  GET    /patients/me/medical-reports               — list (filterable by type)
  POST   /patients/me/medical-reports               — create structured record (no file)
  POST   /patients/me/medical-reports/upload        — upload with file attachment
  GET    /patients/me/medical-reports/{id}          — detail
  PUT    /patients/me/medical-reports/{id}          — update metadata
  GET    /patients/me/medical-reports/{id}/download — download file
  DELETE /patients/me/medical-reports/{id}          — soft-delete
"""

from datetime import datetime
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, DatabaseSession, get_current_patient
from app.models.patient import Patient
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.medical_report import (
    MedicalReportCreate,
    MedicalReportListItem,
    MedicalReportResponse,
    MedicalReportUpdate,
    ReportType,
)
from app.services.medical_report_service import MedicalReportService

router = APIRouter()


def _to_list_item(r) -> MedicalReportListItem:
    return MedicalReportListItem(
        id=r.id,
        title=r.title,
        report_type=r.report_type,
        report_date=r.report_date,
        facility_name=r.facility_name,
        file_name=r.file_name,
        file_type=r.file_type,
        is_abnormal=r.is_abnormal,
        requires_followup=r.requires_followup,
        is_private=r.is_private,
        has_file=bool(r.file_url),
        reference_number=r.reference_number,
        created_at=r.created_at,
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get(
    "/me/medical-reports",
    response_model=PaginatedResponse[MedicalReportListItem],
    summary="List my medical reports",
    description=(
        "Returns all medical reports for the authenticated patient. "
        "Filter by `report_type` to power each dashboard tab:\n"
        "- `lab_result` → Lab Results tab\n"
        "- `prescription` → Prescriptions\n"
        "- `imaging` → Imaging (X-ray, MRI, CT)\n"
        "- `medical_certificate` → Certificates\n"
        "- `medical_travel` → Travel documents"
    ),
)
async def list_medical_reports(
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
    report_type: Optional[ReportType] = Query(default=None, description="Filter by report type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = MedicalReportService(db)
    reports, total = await service.list_reports(
        patient_id=patient.id,
        report_type=report_type,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create([_to_list_item(r) for r in reports], total, page, page_size)


# ---------------------------------------------------------------------------
# Create (structured, no file)
# ---------------------------------------------------------------------------

@router.post(
    "/me/medical-reports",
    response_model=MedicalReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a structured medical report record",
    description="Use this to create a report without a file (e.g., manually entered lab values or prescription text). Use `/upload` for file-based reports.",
)
async def create_medical_report(
    data: MedicalReportCreate,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    service = MedicalReportService(db)
    try:
        return await service.create_report(
            patient_id=patient.id,
            data=data,
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Upload with file
# ---------------------------------------------------------------------------

@router.post(
    "/me/medical-reports/upload",
    response_model=MedicalReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a medical report file",
    description=(
        "Upload a lab report, prescription, imaging result, or certificate as a file attachment. "
        "Supported: PDF, JPG, PNG, DICOM, DOCX, TXT. Max size: 20 MB."
    ),
)
async def upload_medical_report(
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
    file: Annotated[UploadFile, File(description="Report file (PDF, JPG, PNG, DICOM, max 20 MB)")],
    title: Annotated[str, Form(description="Report title, e.g. 'Blood CBC — March 2026'")],
    report_type: Annotated[str, Form(description="lab_result | imaging | prescription | medical_certificate | medical_travel | other")],
    report_date: Annotated[datetime, Form(description="Date the report was issued (ISO 8601)")],
    description: Annotated[Optional[str], Form()] = None,
    facility_name: Annotated[Optional[str], Form(description="Hospital or lab that issued the report")] = None,
    performing_doctor: Annotated[Optional[str], Form(description="Doctor who ordered/signed the report")] = None,
    interpretation: Annotated[Optional[str], Form(description="Doctor's interpretation or notes")] = None,
    is_abnormal: Annotated[bool, Form(description="Flag if results are out of normal range")] = False,
    requires_followup: Annotated[bool, Form(description="Flag if follow-up action is needed")] = False,
    is_private: Annotated[bool, Form(description="If true, only visible to the patient")] = False,
    consultation_id: Annotated[Optional[UUID], Form()] = None,
    doctor_id: Annotated[Optional[UUID], Form()] = None,
):
    allowed_types = {
        "lab_result", "imaging", "prescription",
        "medical_certificate", "medical_travel", "other",
    }
    if report_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid report_type '{report_type}'. Must be one of: {sorted(allowed_types)}",
        )

    service = MedicalReportService(db)
    try:
        return await service.upload_report(
            patient_id=patient.id,
            file=file,
            title=title,
            report_type=report_type,
            report_date=report_date,
            description=description,
            facility_name=facility_name,
            performing_doctor=performing_doctor,
            interpretation=interpretation,
            is_abnormal=is_abnormal,
            requires_followup=requires_followup,
            is_private=is_private,
            consultation_id=consultation_id,
            doctor_id=doctor_id,
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------

@router.get(
    "/me/medical-reports/{report_id}",
    response_model=MedicalReportResponse,
    summary="Get a medical report",
)
async def get_medical_report(
    report_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    service = MedicalReportService(db)
    report = await service.get_report(report_id, patient.id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


# ---------------------------------------------------------------------------
# Update metadata
# ---------------------------------------------------------------------------

@router.put(
    "/me/medical-reports/{report_id}",
    response_model=MedicalReportResponse,
    summary="Update report metadata",
    description="Update title, interpretation, flags, etc. Does NOT replace the file.",
)
async def update_medical_report(
    report_id: UUID,
    data: MedicalReportUpdate,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    service = MedicalReportService(db)
    try:
        return await service.update_report(
            report_id=report_id,
            patient_id=patient.id,
            data=data,
            updated_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# Download file
# ---------------------------------------------------------------------------

@router.get(
    "/me/medical-reports/{report_id}/download",
    summary="Download the report file",
    description="Returns the raw file (PDF, image, etc.). 404 if no file is attached.",
    response_class=FileResponse,
)
async def download_medical_report(
    report_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    service = MedicalReportService(db)
    file_path = await service.get_file_path(report_id, patient.id)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No file attached to this report or file not found on disk",
        )
    report = await service.get_report(report_id, patient.id)
    return FileResponse(
        path=file_path,
        filename=report.file_name or f"report_{report_id}",
        media_type=report.file_type or "application/octet-stream",
    )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete(
    "/me/medical-reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a medical report",
    description="Soft-deletes the record and removes the file from disk.",
)
async def delete_medical_report(
    report_id: UUID,
    current_user: CurrentUser,
    patient: Annotated[Patient, Depends(get_current_patient)],
    db: DatabaseSession,
):
    service = MedicalReportService(db)
    try:
        await service.delete_report(report_id, patient.id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
