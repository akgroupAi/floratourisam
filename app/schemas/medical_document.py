"""Medical document schemas for patient document management."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


class DocumentType(str, Enum):
    """Document type enumeration."""

    LAB_REPORT = "lab_report"
    PRESCRIPTION = "prescription"
    XRAY = "xray"
    MRI_SCAN = "mri_scan"
    CT_SCAN = "ct_scan"
    ULTRASOUND = "ultrasound"
    BLOOD_TEST = "blood_test"
    MEDICAL_CERTIFICATE = "medical_certificate"
    DISCHARGE_SUMMARY = "discharge_summary"
    VACCINATION_RECORD = "vaccination_record"
    OTHER = "other"


class DocumentUploadResponse(BaseSchema):
    """Response schema for document upload."""

    id: UUID
    title: str
    document_type: str
    file_name: str
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="MIME type")
    upload_date: datetime
    download_url: str


class DocumentListItem(BaseSchema):
    """Schema for document list item."""

    id: UUID
    title: str
    document_type: str
    file_name: str
    file_size: int
    upload_date: datetime
    download_url: str
    is_private: bool = False


class DocumentDetailResponse(BaseSchema):
    """Detailed document response schema."""

    id: UUID
    title: str
    document_type: str
    description: Optional[str] = None
    file_name: str
    file_size: int
    file_type: str
    upload_date: datetime
    report_date: datetime
    facility_name: Optional[str] = None
    performing_doctor: Optional[str] = None
    interpretation: Optional[str] = None
    is_abnormal: bool = False
    requires_followup: bool = False
    is_private: bool = False
    download_url: str
