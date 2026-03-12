"""Apartment management endpoints for admin panel."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.apartment import Apartment
from app.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter()


# ============== SCHEMAS ==============


class ApartmentCreate(BaseModel):
    """Schema for creating an apartment."""

    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = None
    bedroom_type: str = Field("studio", description="studio, 1BR, 2BR, 3BR, 4BR+")
    capacity: int = Field(2, ge=1)
    price_per_night: Optional[float] = Field(None, gt=0)
    price_per_week: Optional[float] = Field(None, gt=0)
    price_per_month: Optional[float] = Field(None, gt=0)
    currency: str = "USD"
    address_line1: str = Field(..., min_length=2)
    address_line2: Optional[str] = None
    city: str = Field(..., min_length=2)
    state: Optional[str] = None
    country: str = Field(..., min_length=2)
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    amenities: Optional[List[str]] = None
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    nearby_places: Optional[dict] = None
    priority: int = 0
    is_active: bool = True
    is_available: bool = True
    is_featured: bool = False
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class ApartmentUpdate(BaseModel):
    """Schema for updating an apartment."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = None
    bedroom_type: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=1)
    price_per_night: Optional[float] = Field(None, gt=0)
    price_per_week: Optional[float] = Field(None, gt=0)
    price_per_month: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    amenities: Optional[List[str]] = None
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    nearby_places: Optional[dict] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    is_available: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_verified: Optional[bool] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class ApartmentResponse(BaseModel):
    """Schema for apartment response."""

    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    bedroom_type: str
    capacity: int
    price_per_night: Optional[float] = None
    price_per_week: Optional[float] = None
    price_per_month: Optional[float] = None
    currency: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    country: str
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    amenities: Optional[List[str]] = None
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    nearby_places: Optional[dict] = None
    rating: Optional[float] = None
    total_reviews: int = 0
    priority: int = 0
    is_active: bool
    is_available: bool
    is_featured: bool = False
    is_verified: bool = False
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    class Config:
        from_attributes = True


# ============== APARTMENT KPIs ==============


@router.get("/totals", dependencies=[RequireAdmin])
async def get_apartment_totals(db: DatabaseSession):
    """Get apartment KPI totals."""
    total = await db.execute(
        select(func.count(Apartment.id)).where(Apartment.is_deleted == False)
    )
    active = await db.execute(
        select(func.count(Apartment.id)).where(
            Apartment.is_deleted == False, Apartment.is_active == True
        )
    )
    available = await db.execute(
        select(func.count(Apartment.id)).where(
            Apartment.is_deleted == False, Apartment.is_available == True
        )
    )
    featured = await db.execute(
        select(func.count(Apartment.id)).where(
            Apartment.is_deleted == False, Apartment.is_featured == True
        )
    )
    return {
        "total_apartments": total.scalar() or 0,
        "active_apartments": active.scalar() or 0,
        "available_apartments": available.scalar() or 0,
        "featured_apartments": featured.scalar() or 0,
    }


# ============== APARTMENT CRUD ==============


@router.get("", response_model=PaginatedResponse[ApartmentResponse], dependencies=[RequireAdmin])
async def list_apartments(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    city: Optional[str] = None,
    bedroom_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_available: Optional[bool] = None,
):
    """List all apartments with filtering."""
    query = select(Apartment).where(Apartment.is_deleted == False)

    if search:
        query = query.where(
            or_(
                Apartment.name.ilike(f"%{search}%"),
                Apartment.city.ilike(f"%{search}%"),
            )
        )
    if city:
        query = query.where(Apartment.city.ilike(f"%{city}%"))
    if bedroom_type:
        query = query.where(Apartment.bedroom_type == bedroom_type)
    if is_active is not None:
        query = query.where(Apartment.is_active == is_active)
    if is_available is not None:
        query = query.where(Apartment.is_available == is_available)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(Apartment.priority.desc(), Apartment.name)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    apartments = result.scalars().all()

    return PaginatedResponse.create(apartments, total, page, page_size)


@router.post(
    "",
    response_model=ApartmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireAdmin],
)
async def create_apartment(
    data: ApartmentCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a new apartment."""
    existing = await db.execute(select(Apartment).where(Apartment.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apartment with slug '{data.slug}' already exists",
        )

    apartment = Apartment(**data.model_dump(), created_by=current_user.id)
    db.add(apartment)
    await db.commit()
    await db.refresh(apartment)
    return apartment


@router.get("/{apartment_id}", response_model=ApartmentResponse, dependencies=[RequireAdmin])
async def get_apartment(apartment_id: UUID, db: DatabaseSession):
    """Get apartment details."""
    result = await db.execute(
        select(Apartment).where(
            Apartment.id == apartment_id, Apartment.is_deleted == False
        )
    )
    apartment = result.scalar_one_or_none()
    if not apartment:
        raise HTTPException(status_code=404, detail="Apartment not found")
    return apartment


@router.put("/{apartment_id}", response_model=ApartmentResponse, dependencies=[RequireAdmin])
async def update_apartment(
    apartment_id: UUID,
    data: ApartmentUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update apartment."""
    result = await db.execute(
        select(Apartment).where(
            Apartment.id == apartment_id, Apartment.is_deleted == False
        )
    )
    apartment = result.scalar_one_or_none()
    if not apartment:
        raise HTTPException(status_code=404, detail="Apartment not found")

    if data.slug and data.slug != apartment.slug:
        existing = await db.execute(
            select(Apartment).where(
                Apartment.slug == data.slug, Apartment.id != apartment_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Apartment with slug '{data.slug}' already exists",
            )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(apartment, field, value)

    apartment.updated_by = current_user.id
    await db.commit()
    await db.refresh(apartment)
    return apartment


@router.delete("/{apartment_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_apartment(
    apartment_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Soft delete an apartment."""
    result = await db.execute(
        select(Apartment).where(
            Apartment.id == apartment_id, Apartment.is_deleted == False
        )
    )
    apartment = result.scalar_one_or_none()
    if not apartment:
        raise HTTPException(status_code=404, detail="Apartment not found")

    apartment.is_deleted = True
    apartment.deleted_by = current_user.id
    await db.commit()
    return MessageResponse(message="Apartment deleted successfully")
