"""Apartment management endpoints for admin panel."""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin, RequireApartmentManager
from app.models.apartment import Apartment
from app.models.user import User
from app.schemas.apartment import (
    ApartmentCalendarDay,
    ApartmentCalendarUpdate,
    ApartmentCalendarUpdateResponse,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.booking_service import BookingService
from app.schemas.review import (
    AdminReviewApprove,
    AdminReviewListResponse,
    AdminReviewResponse,
    ReviewListItem,
    ReviewResponse,
)
from app.services.review_service import ReviewService
from app.utils.enums import UserRole
from app.utils.resource_auth import check_resource_access, filter_resources_by_user

router = APIRouter()


# ============== SCHEMAS ==============


class ApartmentCreate(BaseModel):
    """Schema for creating an apartment."""

    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = None
    bedroom_type: str = Field("studio", description="studio, 1BR, 2BR, 3BR, 4BR+")
    property_type: Optional[str] = Field(None, description="Entire home, Private room, Shared room")
    capacity: int = Field(2, ge=1)
    bedrooms: int = Field(1, ge=0)
    beds: int = Field(1, ge=0)
    bathrooms: int = Field(1, ge=0)
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
    phone: Optional[str] = None
    email: Optional[str] = None
    distance_to_hospital_km: Optional[float] = None
    nearest_hospital: Optional[str] = None
    amenities: Optional[List[str]] = None
    medical_amenities: Optional[List[str]] = None
    highlights: Optional[List[dict]] = Field(None, description='[{"icon": "hospital", "title": "Steps from hospital", "description": "300m walk"}]')
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    nearby_places: Optional[dict] = None
    check_in_time: Optional[str] = Field(None, description="HH:MM format")
    check_out_time: Optional[str] = Field(None, description="HH:MM format")
    house_rules: Optional[List[str]] = Field(None, description='["Children welcome", "No pets"]')
    safety_features: Optional[List[str]] = Field(None, description='["Smoke alarm", "Carbon monoxide alarm"]')
    cancellation_policy: Optional[str] = None
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
    property_type: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=1)
    bedrooms: Optional[int] = Field(None, ge=0)
    beds: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
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
    phone: Optional[str] = None
    email: Optional[str] = None
    distance_to_hospital_km: Optional[float] = None
    nearest_hospital: Optional[str] = None
    amenities: Optional[List[str]] = None
    medical_amenities: Optional[List[str]] = None
    highlights: Optional[List[dict]] = None
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    nearby_places: Optional[dict] = None
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    house_rules: Optional[List[str]] = None
    safety_features: Optional[List[str]] = None
    cancellation_policy: Optional[str] = None
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
    property_type: Optional[str] = None
    capacity: int
    bedrooms: int = 1
    beds: int = 1
    bathrooms: int = 1
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
    phone: Optional[str] = None
    email: Optional[str] = None
    distance_to_hospital_km: Optional[float] = None
    nearest_hospital: Optional[str] = None
    amenities: Optional[List[str]] = None
    medical_amenities: Optional[List[str]] = None
    highlights: Optional[list] = None
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    nearby_places: Optional[dict] = None
    rating: Optional[float] = None
    total_reviews: int = 0
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    house_rules: Optional[list] = None
    safety_features: Optional[list] = None
    cancellation_policy: Optional[str] = None
    priority: int = 0
    is_active: bool
    is_available: bool
    is_featured: bool = False
    is_verified: bool = False
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    class Config:
        from_attributes = True


class AssignApartmentManagerRequest(BaseModel):
    """Request to assign an apartment manager."""
    manager_id: Optional[UUID] = Field(None, description="Apartment manager ID, or None to unassign")


class ManagerResponse(BaseModel):
    """Response with manager info."""
    user_id: UUID
    email: str
    full_name: str
    role: Optional[str] = None


class ApartmentWithManagerResponse(BaseModel):
    """Apartment response with manager information."""
    id: UUID
    name: str
    city: str
    manager: Optional[ManagerResponse] = None

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


@router.get("", dependencies=[RequireApartmentManager])
async def list_apartments(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    city: Optional[str] = None,
    bedroom_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_available: Optional[bool] = None,
    with_manager: bool = Query(False, description="Include manager information"),
):
    """
    List apartments.
    - Super Admin/Admin: See all apartments
    - Apartment Manager: See only their assigned apartments
    - with_manager=true: Include manager details in response
    """
    query = select(Apartment).where(Apartment.is_deleted == False)
    
    # Filter by user access
    query = await filter_resources_by_user(Apartment, current_user, query)

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

    # Return with or without manager info based on parameter
    if with_manager:
        items = []
        for apartment in apartments:
            manager_data = None
            if apartment.manager_id:
                manager_result = await db.execute(
                    select(User).where(User.id == apartment.manager_id)
                )
                manager = manager_result.scalar_one_or_none()
                if manager:
                    manager_data = ManagerResponse(
                        user_id=manager.id,
                        email=manager.email,
                        full_name=manager.full_name,
                        role=manager.role
                    )
            items.append(ApartmentWithManagerResponse(
                id=apartment.id,
                name=apartment.name,
                city=apartment.city,
                manager=manager_data
            ))
        return PaginatedResponse.create(items, total, page, page_size)
    else:
        items = [ApartmentResponse.model_validate(a) for a in apartments]
        return PaginatedResponse.create(items, total, page, page_size)


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


# ============== REVIEWS ==============


@router.get(
    "/{apartment_id}/reviews",
    response_model=AdminReviewListResponse,
    dependencies=[RequireAdmin],
)
async def list_apartment_reviews_admin(
    apartment_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_approved: Optional[bool] = None,
):
    """List all reviews for an apartment (admin) with summary stats."""
    service = ReviewService(db)
    
    # Get paginated reviews
    reviews, total = await service.admin_list(
        page=page,
        page_size=page_size,
        entity_type="apartment",
        entity_id=apartment_id,
        is_approved=is_approved,
    )
    
    # Get summary stats
    summary = await service.get_entity_summary(entity_type="apartment", entity_id=apartment_id)
    
    return AdminReviewListResponse(
        average_rating=summary.average_rating,
        total_reviews=summary.total_reviews,
        rating_breakdown=summary.rating_breakdown,
        verified_count=summary.verified_count,
        items=reviews,
        total=total,
        page=page,
        page_size=page_size,
    )



@router.patch(
    "/reviews/{review_id}/approve",
    response_model=ReviewResponse,
    dependencies=[RequireAdmin],
)
async def approve_review(
    review_id: UUID,
    data: AdminReviewApprove,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Approve or reject a review."""
    service = ReviewService(db)
    try:
        return await service.admin_approve(
            review_id=review_id, data=data, admin_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/reviews/{review_id}/respond",
    response_model=ReviewResponse,
    dependencies=[RequireAdmin],
)
async def respond_to_review(
    review_id: UUID,
    data: AdminReviewResponse,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Post an official response to a review."""
    service = ReviewService(db)
    try:
        return await service.admin_respond(
            review_id=review_id,
            response_text=data.response_text,
            admin_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/reviews/{review_id}",
    response_model=MessageResponse,
    dependencies=[RequireAdmin],
)
async def delete_review_admin(
    review_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Delete a review (admin)."""
    service = ReviewService(db)
    try:
        await service.admin_delete(review_id=review_id, admin_id=current_user.id)
        return MessageResponse(message="Review deleted successfully")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============== MANAGER ASSIGNMENT ==============


@router.post("/{apartment_id}/assign-manager", response_model=dict, dependencies=[RequireAdmin])
async def assign_apartment_manager(
    apartment_id: UUID,
    request: AssignApartmentManagerRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Assign or unassign an apartment manager (admin only)."""
    # Verify apartment exists
    result = await db.execute(
        select(Apartment).where(Apartment.id == apartment_id, Apartment.is_deleted == False)
    )
    apartment = result.scalar_one_or_none()
    if not apartment:
        raise HTTPException(status_code=404, detail="Apartment not found")
    
    # If assigning, verify manager exists and has apartment_manager role
    if request.manager_id:
        result = await db.execute(
            select(User).where(User.id == request.manager_id)
        )
        manager = result.scalar_one_or_none()
        if not manager:
            raise HTTPException(status_code=404, detail="Manager user not found")
        if manager.role != UserRole.APARTMENT_MANAGER.value:
            raise HTTPException(
                status_code=400,
                detail="User must have apartment_manager role"
            )
    
    # Update apartment manager
    apartment.manager_id = request.manager_id
    apartment.updated_by = current_user.id
    await db.commit()
    await db.refresh(apartment)
    
    action = "assigned" if request.manager_id else "unassigned"
    return {
        "message": f"Apartment manager {action}",
        "apartment_id": str(apartment.id),
        "manager_id": str(apartment.manager_id) if apartment.manager_id else None
    }


@router.get("/{apartment_id}/manager", response_model=Optional[ManagerResponse], dependencies=[RequireAdmin])
async def get_apartment_manager(
    apartment_id: UUID,
    db: DatabaseSession,
):
    """Get the manager assigned to an apartment."""
    result = await db.execute(
        select(Apartment).where(Apartment.id == apartment_id, Apartment.is_deleted == False)
    )
    apartment = result.scalar_one_or_none()
    if not apartment:
        raise HTTPException(status_code=404, detail="Apartment not found")
    
    if not apartment.manager_id:
        return None
    
    result = await db.execute(
        select(User).where(User.id == apartment.manager_id)
    )
    manager = result.scalar_one_or_none()
    return manager


# ============== RATE & AVAILABILITY CALENDAR ==============
#
# Apartments previously had only an is_available boolean — no way to block dates, set a
# seasonal rate, or require a minimum stay.


async def _get_apartment_or_404(db, apartment_id: UUID) -> Apartment:
    apartment = (
        await db.execute(
            select(Apartment).where(
                Apartment.id == apartment_id,
                Apartment.is_deleted == False,
            )
        )
    ).scalar_one_or_none()
    if not apartment:
        raise HTTPException(status_code=404, detail="Apartment not found")
    return apartment


@router.get(
    "/{apartment_id}/calendar",
    response_model=List[ApartmentCalendarDay],
    dependencies=[RequireAdmin],
    summary="Read the rate and availability calendar",
)
async def get_apartment_calendar(
    apartment_id: UUID,
    db: DatabaseSession,
    start_date: date = Query(..., description="First night (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Exclusive — the first night NOT included"),
):
    """
    One row per night with price, minimum stay, whether it is blocked, and whether it is
    already booked.

    Nights with no override fall back to the apartment's `price_per_night` and
    `minimum_nights`, and come back with `has_override: false`.
    """
    await _get_apartment_or_404(db, apartment_id)
    if end_date <= start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")
    if (end_date - start_date).days > 400:
        raise HTTPException(status_code=400, detail="Range cannot exceed 400 nights")

    return await BookingService(db).get_apartment_calendar(apartment_id, start_date, end_date)


@router.put(
    "/{apartment_id}/calendar",
    response_model=ApartmentCalendarUpdateResponse,
    dependencies=[RequireAdmin],
    summary="Set rates, minimum stay, or blocks across a date range",
)
async def set_apartment_calendar(
    apartment_id: UUID,
    data: ApartmentCalendarUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    Bulk upsert the calendar. Only the fields you send are changed.

    Peak-season pricing with a longer minimum stay:

    ```json
    {"start_date": "2026-12-20", "end_date": "2027-01-05",
     "price": 4500, "minimum_nights": 7, "notes": "Festive period"}
    ```

    Block for maintenance with `"is_blocked": true`; reopen with `false`.
    """
    await _get_apartment_or_404(db, apartment_id)
    if (data.end_date - data.start_date).days > 400:
        raise HTTPException(status_code=400, detail="Range cannot exceed 400 nights")

    try:
        days = await BookingService(db).set_apartment_calendar(
            apartment_id=apartment_id,
            start=data.start_date,
            end=data.end_date,
            updated_by=current_user.id,
            price=data.price,
            is_blocked=data.is_blocked,
            minimum_nights=data.minimum_nights,
            notes=data.notes,
            weekdays=data.weekdays,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ApartmentCalendarUpdateResponse(
        apartment_id=apartment_id,
        days_updated=days,
        start_date=data.start_date,
        end_date=data.end_date,
    )


@router.delete(
    "/{apartment_id}/calendar",
    response_model=MessageResponse,
    dependencies=[RequireAdmin],
    summary="Clear calendar overrides for a date range",
)
async def clear_apartment_calendar(
    apartment_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    start_date: date = Query(...),
    end_date: date = Query(..., description="Exclusive"),
):
    """Remove overrides so those nights revert to the apartment's defaults."""
    await _get_apartment_or_404(db, apartment_id)
    if end_date <= start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    cleared = await BookingService(db).clear_apartment_calendar(
        apartment_id, start_date, end_date, deleted_by=current_user.id
    )
    return MessageResponse(message=f"Cleared {cleared} calendar day(s)")
