"""Career models — job positions and applications."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class JobPosition(BaseModel):
    """A job position / open vacancy."""

    __tablename__ = "job_positions"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(100), nullable=False)  # Engineering, Marketing, etc.
    location: Mapped[str] = mapped_column(String(200), nullable=False)  # Bangalore, Remote, etc.
    employment_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="full_time"
    )  # full_time, part_time, contract, internship
    experience_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # entry, mid, senior
    salary_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="INR")
    show_salary: Mapped[bool] = mapped_column(Boolean, default=False)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # HTML / rich text
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # HTML / rich text
    responsibilities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    benefits: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # e.g. ["react", "python"]
    apply_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # external apply link

    applications = relationship("JobApplication", back_populates="position", lazy="selectin")


class JobApplication(BaseModel):
    """An application submitted for a job position."""

    __tablename__ = "job_applications"

    position_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_positions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Applicant info (may or may not be a registered user)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    resume_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cover_letter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    experience_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_company: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(30), default="submitted", nullable=False, index=True
    )  # submitted, reviewing, shortlisted, interview, offered, hired, rejected
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    position = relationship("JobPosition", back_populates="applications", lazy="selectin")
