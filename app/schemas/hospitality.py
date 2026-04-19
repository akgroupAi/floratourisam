"""Schemas for the dynamic Hospitality / Beyond Medical Care section."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


# ── Grid card (HospitalityService) ────────────────────────────

class HospitalityServiceBase(BaseSchema):
    key: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=500)
    icon: Optional[str] = None
    image_url: Optional[str] = None
    highlight: Optional[str] = None
    url: Optional[str] = None
    display_order: int = 0
    is_active: bool = True


class HospitalityServiceCreate(HospitalityServiceBase):
    pass


class HospitalityServiceUpdate(BaseSchema):
    key: Optional[str] = Field(None, min_length=1, max_length=100)
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    icon: Optional[str] = None
    image_url: Optional[str] = None
    highlight: Optional[str] = None
    url: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class HospitalityServiceResponse(HospitalityServiceBase):
    id: UUID


# ── Detail page (HospitalityPage) ────────────────────────────

class HospitalityPageBase(BaseSchema):
    slug: str = Field(..., min_length=1, max_length=255)

    # Hero
    hero_title: str = Field(..., min_length=1, max_length=255)
    hero_subtitle: Optional[str] = None
    hero_background_image: Optional[str] = None
    hero_breadcrumb: Optional[List[Dict[str, str]]] = None
    hero_ctas: Optional[List[Dict[str, str]]] = None

    # Stats
    stats: Optional[List[Dict[str, str]]] = None

    # Features / What's Included
    features_title: Optional[str] = None
    features_subtitle: Optional[str] = None
    features: Optional[List[Dict[str, str]]] = None

    # How It Works
    steps_title: Optional[str] = None
    steps_subtitle: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None

    # Gallery
    gallery_title: Optional[str] = None
    gallery_subtitle: Optional[str] = None
    gallery_images: Optional[List[str]] = None

    # Testimonials
    testimonials_title: Optional[str] = None
    testimonials_subtitle: Optional[str] = None
    testimonial_category: Optional[str] = None

    # FAQ
    faq_title: Optional[str] = None
    faq_category: Optional[str] = None

    # SEO
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    # Extra sections
    extra_sections: Optional[Dict[str, Any]] = None

    is_active: bool = True


class HospitalityPageCreate(HospitalityPageBase):
    service_id: UUID


class HospitalityPageUpdate(BaseSchema):
    slug: Optional[str] = Field(None, min_length=1, max_length=255)
    hero_title: Optional[str] = Field(None, min_length=1, max_length=255)
    hero_subtitle: Optional[str] = None
    hero_background_image: Optional[str] = None
    hero_breadcrumb: Optional[List[Dict[str, str]]] = None
    hero_ctas: Optional[List[Dict[str, str]]] = None
    stats: Optional[List[Dict[str, str]]] = None
    features_title: Optional[str] = None
    features_subtitle: Optional[str] = None
    features: Optional[List[Dict[str, str]]] = None
    steps_title: Optional[str] = None
    steps_subtitle: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None
    gallery_title: Optional[str] = None
    gallery_subtitle: Optional[str] = None
    gallery_images: Optional[List[str]] = None
    testimonials_title: Optional[str] = None
    testimonials_subtitle: Optional[str] = None
    testimonial_category: Optional[str] = None
    faq_title: Optional[str] = None
    faq_category: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    extra_sections: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class HospitalityPageResponse(HospitalityPageBase):
    id: UUID
    service_id: UUID
