"""Medical report schemas.

Report types (report_type field):
  lab_result         → Lab Results tab
  imaging            → X-ray, MRI, CT, Ultrasound
  prescription       → Doctor prescriptions
  medical_certificate → Fit-to-fly, fit-for-surgery certificates
  medical_travel     → Travel clearance, insurance letters
  other              → Any other clinical document
"""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema

# All allowed report type values
ReportType = Literal[
    "lab_result",
    "imaging",
    "prescription",
    "medical_certificate",
    "medical_travel",
    "other",
]


class MedicalReportCreate(BaseSchema):
    """Payload for uploading / creating a medical report record."""

    title: str = Field(..., min_length=1, max_length=255)
    report_type: ReportType
    description: Optional[str] = Field(default=None, max_length=2000)
    report_date: datetime
    facility_name: Optional[str] = Field(default=None, max_length=255)
    facility_address: Optional[str] = Field(default=None, max_length=500)
    performing_doctor: Optional[str] = Field(default=None, max_length=255)
    content: Optional[str] = None
    interpretation: Optional[str] = None
    is_abnormal: bool = False
    requires_followup: bool = False
    is_private: bool = False
    consultation_id: Optional[UUID] = None
    doctor_id: Optional[UUID] = None


class MedicalReportUpdate(BaseSchema):
    """Partial update for a medical report."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    report_date: Optional[datetime] = None
    facility_name: Optional[str] = None
    performing_doctor: Optional[str] = None
    content: Optional[str] = None
    interpretation: Optional[str] = None
    is_abnormal: Optional[bool] = None
    requires_followup: Optional[bool] = None
    is_private: Optional[bool] = None


class MedicalReportResponse(BaseSchema):
    """Full medical report response."""

    id: UUID
    patient_id: UUID
    doctor_id: Optional[UUID] = None
    consultation_id: Optional[UUID] = None

    title: str
    report_type: str
    description: Optional[str] = None

    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size_bytes: Optional[int] = None

    content: Optional[str] = None
    interpretation: Optional[str] = None
    is_abnormal: bool
    requires_followup: bool
    is_private: bool

    report_date: datetime
    facility_name: Optional[str] = None
    facility_address: Optional[str] = None
    performing_doctor: Optional[str] = None

    reference_number: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class MedicalReportListItem(BaseSchema):
    """Compact item for list views."""

    id: UUID
    title: str
    report_type: str
    report_date: datetime
    facility_name: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    is_abnormal: bool
    requires_followup: bool
    is_private: bool
    has_file: bool
    reference_number: Optional[str] = None
    created_at: datetime
