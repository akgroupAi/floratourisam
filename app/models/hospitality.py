"""Hospitality section models — Beyond Medical Care."""

import uuid
from typing import Optional, List

from sqlalchemy import Boolean, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class HospitalityService(BaseModel):
    """One of the 9 cards in the 'Beyond Medical Care' grid.

    Each row represents a service card (e.g. Apartments & Stays,
    Restaurants & Dining, Forex Exchange, etc.).
    """

    __tablename__ = "hospitality_services"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    highlight: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. "500+ Stays"
    url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # frontend route

    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Link to the detail page (optional)
    page: Mapped[Optional["HospitalityPage"]] = relationship(
        "HospitalityPage", back_populates="service", uselist=False, lazy="selectin",
    )


class HospitalityPage(BaseModel):
    """Internal detail page for a hospitality service.

    Stores hero, stats, features, how-it-works, gallery config, and
    links to FAQs/testimonials by category.
    """

    __tablename__ = "hospitality_pages"

    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hospitality_services.id", ondelete="CASCADE"),
        unique=True, nullable=False,
    )
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # Hero section
    hero_title: Mapped[str] = mapped_column(String(255), nullable=False)
    hero_subtitle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hero_background_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    hero_breadcrumb: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # [{label, url}]
    hero_ctas: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # [{text, url, variant}]

    # Stats bar  — [{value, label}]
    stats: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # What's Included / Features
    features_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    features_subtitle: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    features: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # [{icon, title, description}]

    # How It Works
    steps_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    steps_subtitle: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    steps: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # [{number, title, description}]

    # Gallery config
    gallery_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gallery_subtitle: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    gallery_images: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # [url, ...]

    # Testimonials config
    testimonials_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    testimonials_subtitle: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    testimonial_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # FAQ config
    faq_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    faq_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # maps to FAQ.category

    # SEO
    meta_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Extra sections (escape hatch for custom content)
    extra_sections: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationship back to service card
    service: Mapped["HospitalityService"] = relationship(
        "HospitalityService", back_populates="page", lazy="selectin",
    )
