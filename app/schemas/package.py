"""Medical package schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import BaseSchema
from app.utils.enums import PackageCategory, PackageItemType


# ---------------------------------------------------------------------------
# PackageItem schemas
# ---------------------------------------------------------------------------

class PackageItemCreate(BaseModel):
    """Create a single item within a package."""

    item_type: PackageItemType
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    quantity: int = Field(default=1, ge=1)
    unit: Optional[str] = Field(default=None, max_length=50)
    display_order: int = Field(default=0, ge=0)


class PackageItemUpdate(BaseModel):
    """Update a single item within a package."""

    item_type: Optional[PackageItemType] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    quantity: Optional[int] = Field(default=None, ge=1)
    unit: Optional[str] = Field(default=None, max_length=50)
    display_order: Optional[int] = Field(default=None, ge=0)


class PackageItemResponse(BaseSchema):
    """Package item response."""

    id: UUID
    package_id: UUID
    item_type: str
    name: str
    description: Optional[str] = None
    quantity: int
    unit: Optional[str] = None
    display_order: int
    created_at: datetime


# ---------------------------------------------------------------------------
# MedicalPackage schemas
# ---------------------------------------------------------------------------

class PackageCreate(BaseModel):
    """Create a medical package."""

    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    short_description: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = None
    category: PackageCategory = PackageCategory.GENERAL
    price: float = Field(..., gt=0)
    discounted_price: Optional[float] = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    duration_days: int = Field(default=1, ge=1)
    hospital_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    image_url: Optional[str] = Field(default=None, max_length=500)
    gallery: Optional[List[str]] = None
    is_active: bool = True
    is_featured: bool = False
    max_persons: int = Field(default=1, ge=1, le=20)
    inclusions: Optional[List[str]] = None
    exclusions: Optional[List[str]] = None
    terms_and_conditions: Optional[str] = None
    meta_title: Optional[str] = Field(default=None, max_length=255)
    meta_description: Optional[str] = Field(default=None, max_length=500)
    items: Optional[List[PackageItemCreate]] = None

    @field_validator("discounted_price")
    @classmethod
    def discounted_must_be_less_than_price(cls, v, info):
        if v is not None and "price" in info.data and v >= info.data["price"]:
            raise ValueError("discounted_price must be less than price")
        return v


class PackageUpdate(BaseModel):
    """Update a medical package (all fields optional)."""

    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    slug: Optional[str] = Field(default=None, min_length=2, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    short_description: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = None
    category: Optional[PackageCategory] = None
    price: Optional[float] = Field(default=None, gt=0)
    discounted_price: Optional[float] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    duration_days: Optional[int] = Field(default=None, ge=1)
    hospital_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    image_url: Optional[str] = Field(default=None, max_length=500)
    gallery: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    max_persons: Optional[int] = Field(default=None, ge=1, le=20)
    inclusions: Optional[List[str]] = None
    exclusions: Optional[List[str]] = None
    terms_and_conditions: Optional[str] = None
    meta_title: Optional[str] = Field(default=None, max_length=255)
    meta_description: Optional[str] = Field(default=None, max_length=500)


class PackageListResponse(BaseSchema):
    """Minimal package representation for list views."""

    id: UUID
    name: str
    slug: str
    short_description: Optional[str] = None
    category: str
    price: float
    discounted_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    currency: str
    duration_days: int
    image_url: Optional[str] = None
    is_featured: bool
    hospital_id: Optional[UUID] = None
    hospital_name: Optional[str] = None
    created_at: datetime


class PackageResponse(BaseSchema):
    """Full package detail including items."""

    id: UUID
    name: str
    slug: str
    short_description: Optional[str] = None
    description: Optional[str] = None
    category: str
    price: float
    discounted_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    currency: str
    duration_days: int
    hospital_id: Optional[UUID] = None
    hospital_name: Optional[str] = None
    department_id: Optional[UUID] = None
    department_name: Optional[str] = None
    image_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    is_active: bool
    is_featured: bool
    max_persons: int
    inclusions: Optional[List[str]] = None
    exclusions: Optional[List[str]] = None
    terms_and_conditions: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    items: List[PackageItemResponse] = []
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Booking schemas
# ---------------------------------------------------------------------------

class PackageBookingCreate(BaseModel):
    """Book a medical package."""

    package_id: UUID
    guest_count: int = Field(default=1, ge=1, le=20)
    guest_details: Optional[dict] = None
    special_requests: Optional[str] = Field(default=None, max_length=2000)
    notes: Optional[str] = Field(default=None, max_length=1000)
    discount_code: Optional[str] = Field(default=None, max_length=50)
