"""Career / Job Position schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


# ── Job Position Schemas ──────────────────────────────────────────


class JobPositionCreate(BaseModel):
    title: str = Field(..., max_length=200)
    slug: str = Field(..., max_length=220)
    department: str = Field(..., max_length=100)
    location: str = Field(..., max_length=200)
    employment_type: str = Field(default="full_time", max_length=50)
    experience_level: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = "INR"
    show_salary: bool = False
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    benefits: Optional[str] = None
    is_active: bool = True
    is_featured: bool = False
    sort_order: int = 0
    tags: Optional[list] = None
    apply_url: Optional[str] = None


class JobPositionUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    slug: Optional[str] = Field(None, max_length=220)
    department: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    employment_type: Optional[str] = Field(None, max_length=50)
    experience_level: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    show_salary: Optional[bool] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    benefits: Optional[str] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None
    tags: Optional[list] = None
    apply_url: Optional[str] = None


class JobPositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    department: str
    location: str
    employment_type: str
    experience_level: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    show_salary: bool = False
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    benefits: Optional[str] = None
    is_active: bool = True
    is_featured: bool = False
    sort_order: int = 0
    tags: Optional[list] = None
    apply_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class JobPositionListResponse(BaseModel):
    """Lightweight response for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    department: str
    location: str
    employment_type: str
    experience_level: Optional[str] = None
    is_featured: bool = False
    sort_order: int = 0
    created_at: Optional[datetime] = None


# ── Job Application Schemas ───────────────────────────────────────


class JobApplicationCreate(BaseModel):
    position_id: UUID
    full_name: str = Field(..., max_length=200)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=30)
    resume_url: Optional[str] = None
    cover_letter: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    experience_years: Optional[int] = None
    current_company: Optional[str] = Field(None, max_length=200)
    extra_data: Optional[dict] = None


class JobApplicationStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        description="One of: submitted, reviewing, shortlisted, interview, offered, hired, rejected",
    )
    admin_notes: Optional[str] = None


class JobApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position_id: UUID
    user_id: Optional[UUID] = None
    full_name: str
    email: str
    phone: Optional[str] = None
    resume_url: Optional[str] = None
    cover_letter: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    experience_years: Optional[int] = None
    current_company: Optional[str] = None
    status: str
    admin_notes: Optional[str] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    extra_data: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class JobApplicationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position_id: UUID
    full_name: str
    email: str
    status: str
    experience_years: Optional[int] = None
    current_company: Optional[str] = None
    created_at: Optional[datetime] = None
