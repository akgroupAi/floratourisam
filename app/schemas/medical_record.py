"""Medical record schemas for patient health information."""

from datetime import date
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


# Enums
class ConditionStatus(str, Enum):
    """Medical condition status."""
    ACTIVE = "Active"
    MANAGED = "Managed"
    CONTROLLED = "Controlled"
    RESOLVED = "Resolved"


class Severity(str, Enum):
    """Severity level."""
    MILD = "Mild"
    MODERATE = "Moderate"
    SEVERE = "Severe"


# Medical Condition Schemas
class MedicalConditionCreate(BaseModel):
    """Schema for creating a medical condition."""
    condition_name: str = Field(..., min_length=1, max_length=255)
    diagnosed_date: Optional[date] = None
    status: ConditionStatus = ConditionStatus.ACTIVE
    severity: Optional[Severity] = None
    notes: Optional[str] = None


class MedicalConditionUpdate(BaseModel):
    """Schema for updating a medical condition."""
    condition_name: Optional[str] = Field(None, min_length=1, max_length=255)
    diagnosed_date: Optional[date] = None
    status: Optional[ConditionStatus] = None
    severity: Optional[Severity] = None
    notes: Optional[str] = None


class MedicalConditionResponse(BaseSchema):
    """Schema for medical condition response."""
    id: UUID
    patient_id: UUID
    condition_name: str
    diagnosed_date: Optional[date]
    status: str
    severity: Optional[str]
    notes: Optional[str]


# Allergy Schemas
class AllergyCreate(BaseModel):
    """Schema for creating an allergy."""
    allergen: str = Field(..., min_length=1, max_length=255)
    reaction: Optional[str] = Field(None, max_length=255)
    severity: Severity = Severity.MODERATE
    diagnosed_date: Optional[date] = None
    notes: Optional[str] = None


class AllergyUpdate(BaseModel):
    """Schema for updating an allergy."""
    allergen: Optional[str] = Field(None, min_length=1, max_length=255)
    reaction: Optional[str] = Field(None, max_length=255)
    severity: Optional[Severity] = None
    diagnosed_date: Optional[date] = None
    notes: Optional[str] = None


class AllergyResponse(BaseSchema):
    """Schema for allergy response."""
    id: UUID
    patient_id: UUID
    allergen: str
    reaction: Optional[str]
    severity: str
    diagnosed_date: Optional[date]
    notes: Optional[str]


# Medication Schemas
class MedicationCreate(BaseModel):
    """Schema for creating a medication."""
    medication_name: str = Field(..., min_length=1, max_length=255)
    dosage: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, max_length=100)
    duration: Optional[str] = Field(None, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    prescribing_doctor: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    is_active: bool = True


class MedicationUpdate(BaseModel):
    """Schema for updating a medication."""
    medication_name: Optional[str] = Field(None, min_length=1, max_length=255)
    dosage: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, max_length=100)
    duration: Optional[str] = Field(None, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    prescribing_doctor: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class MedicationResponse(BaseSchema):
    """Schema for medication response."""
    id: UUID
    patient_id: UUID
    medication_name: str
    dosage: Optional[str]
    frequency: Optional[str]
    duration: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    prescribing_doctor: Optional[str]
    notes: Optional[str]
    is_active: bool
