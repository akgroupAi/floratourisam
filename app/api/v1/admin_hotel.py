"""Hotel management endpoints for admin panel."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.hotel import Hotel, Room
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.review import (
    AdminReviewApprove,
    AdminReviewResponse,
    ReviewListItem,
    ReviewResponse,
)
from app.services.review_service import ReviewService

router = APIRouter()


# ============== SCHEMAS ==============


class NearbyRestaurant(BaseModel):
    """Nearby restaurant object."""

    name: str = Field(..., min_length=1, max_length=255)
    cuisine_type: Optional[str] = None
    distance_km: Optional[float] = Field(None, ge=0)
    price_range: Optional[str] = Field(None, description="e.g. '$', '$$', '$$$'")
    address: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)


class NearbyTransport(BaseModel):
    """Nearby transport option object."""

    type: str = Field(..., description="e.g. metro, bus, taxi, airport, train")
    name: str = Field(..., min_length=1, max_length=255)
    distance_km: Optional[float] = Field(None, ge=0)
    description: Optional[str] = None


class HotelCreate(BaseModel):
    """Schema for creating a hotel."""

    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = None
    star_rating: Optional[int] = Field(None, ge=1, le=5)
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: str = Field(..., min_length=2)
    address_line2: Optional[str] = None
    city: str = Field(..., min_length=2)
    state: Optional[str] = None
    country: str = Field(..., min_length=2)
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_to_hospital_km: Optional[float] = None
    nearest_hospital: Optional[str] = None
    amenities: Optional[List[str]] = None
    medical_amenities: Optional[List[str]] = None
    base_price_per_night: Optional[float] = None
    currency: str = "USD"
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    cancellation_policy: Optional[str] = None
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    nearby_restaurants: Optional[List[NearbyRestaurant]] = None
    nearby_transport: Optional[List[NearbyTransport]] = None
    facilities: Optional[dict] = None
    policies: Optional[dict] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    is_active: bool = True
    is_featured: bool = False


class HotelUpdate(BaseModel):
    """Schema for updating a hotel."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = None
    star_rating: Optional[int] = Field(None, ge=1, le=5)
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_to_hospital_km: Optional[float] = None
    nearest_hospital: Optional[str] = None
    amenities: Optional[List[str]] = None
    medical_amenities: Optional[List[str]] = None
    base_price_per_night: Optional[float] = None
    currency: Optional[str] = None
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    cancellation_policy: Optional[str] = None
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    nearby_restaurants: Optional[List[NearbyRestaurant]] = None
    nearby_transport: Optional[List[NearbyTransport]] = None
    facilities: Optional[dict] = None
    policies: Optional[dict] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_verified: Optional[bool] = None


class HotelResponse(BaseModel):
    """Schema for hotel response."""

    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    star_rating: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    country: str
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_to_hospital_km: Optional[float] = None
    nearest_hospital: Optional[str] = None
    amenities: Optional[List[str]] = None
    medical_amenities: Optional[List[str]] = None
    base_price_per_night: Optional[float] = None
    currency: str = "USD"
    rating: Optional[float] = None
    total_reviews: int = 0
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    cancellation_policy: Optional[str] = None
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    nearby_restaurants: Optional[List[NearbyRestaurant]] = None
    nearby_transport: Optional[List[NearbyTransport]] = None
    facilities: Optional[dict] = None
    policies: Optional[dict] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    is_active: bool
    is_featured: bool = False
    is_verified: bool = False

    class Config:
        from_attributes = True


class RoomCreate(BaseModel):
    """Schema for creating a room."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    room_number: str = Field(..., min_length=1, max_length=50)
    room_type: str = Field(..., description="standard, deluxe, suite, etc.")
    description: Optional[str] = None
    max_occupancy: int = Field(2, ge=1)
    bed_type: Optional[str] = None
    bed_count: int = Field(1, ge=1)
    size_sqm: Optional[float] = None
    view: Optional[dict] = None
    amenities: Optional[List[str]] = None
    highlights: Optional[List[str]] = None
    price_per_night: float = Field(..., gt=0)
    total_rooms: int = Field(1, ge=1)
    images: Optional[List[str]] = None
    wheelchair_accessible: bool = False
    medical_equipment_available: bool = False
    is_available: bool = True


class RoomUpdate(BaseModel):
    """Schema for updating a room."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    room_number: Optional[str] = Field(None, min_length=1, max_length=50)
    room_type: Optional[str] = None
    description: Optional[str] = None
    max_occupancy: Optional[int] = Field(None, ge=1)
    bed_type: Optional[str] = None
    bed_count: Optional[int] = Field(None, ge=1)
    size_sqm: Optional[float] = None
    view: Optional[dict] = None
    amenities: Optional[List[str]] = None
    highlights: Optional[List[str]] = None
    price_per_night: Optional[float] = Field(None, gt=0)
    total_rooms: Optional[int] = Field(None, ge=1)
    images: Optional[List[str]] = None
    wheelchair_accessible: Optional[bool] = None
    medical_equipment_available: Optional[bool] = None
    is_available: Optional[bool] = None


class RoomResponse(BaseModel):
    """Schema for room response."""

    id: UUID
    hotel_id: UUID
    name: str
    room_number: Optional[str] = None
    room_type: str
    description: Optional[str] = None
    max_occupancy: int
    bed_type: Optional[str] = None
    bed_count: int
    size_sqm: Optional[float] = None
    view: Optional[dict] = None
    amenities: Optional[List[str]] = None
    highlights: Optional[List[str]] = None
    price_per_night: float
    total_rooms: int
    is_available: bool
    wheelchair_accessible: bool
    medical_equipment_available: bool
    images: Optional[List[str]] = None

    class Config:
        from_attributes = True


# ============== HOTEL KPIs ==============


@router.get("/totals", dependencies=[RequireAdmin])
async def get_hotel_totals(db: DatabaseSession):
    """Get hotel KPI totals."""
    total = await db.execute(
        select(func.count(Hotel.id)).where(Hotel.is_deleted == False)
    )
    active = await db.execute(
        select(func.count(Hotel.id)).where(
            Hotel.is_deleted == False, Hotel.is_active == True
        )
    )
    inactive = await db.execute(
        select(func.count(Hotel.id)).where(
            Hotel.is_deleted == False, Hotel.is_active == False
        )
    )
    featured = await db.execute(
        select(func.count(Hotel.id)).where(
            Hotel.is_deleted == False, Hotel.is_featured == True
        )
    )
    return {
        "total_hotels": total.scalar() or 0,
        "active_hotels": active.scalar() or 0,
        "inactive_hotels": inactive.scalar() or 0,
        "featured_hotels": featured.scalar() or 0,
    }


# ============== HOTEL CRUD ==============


@router.get("", response_model=PaginatedResponse[HotelResponse], dependencies=[RequireAdmin])
async def list_hotels(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    city: Optional[str] = None,
    is_active: Optional[bool] = None,
    star_rating: Optional[int] = None,
):
    """List all hotels with filtering."""
    query = select(Hotel).where(Hotel.is_deleted == False)

    if search:
        query = query.where(
            or_(
                Hotel.name.ilike(f"%{search}%"),
                Hotel.city.ilike(f"%{search}%"),
                Hotel.email.ilike(f"%{search}%"),
            )
        )
    if city:
        query = query.where(Hotel.city.ilike(f"%{city}%"))
    if is_active is not None:
        query = query.where(Hotel.is_active == is_active)
    if star_rating is not None:
        query = query.where(Hotel.star_rating == star_rating)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(Hotel.name)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    hotels = result.scalars().all()

    # Enrich hotels with calculated base prices
    from app.services.hotel_service import HotelService
    service = HotelService(db)
    hotels = await service._enrich_hotels_with_base_prices(list(hotels))

    return PaginatedResponse.create(hotels, total, page, page_size)


@router.post("", response_model=HotelResponse, status_code=status.HTTP_201_CREATED, dependencies=[RequireAdmin])
async def create_hotel(data: HotelCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new hotel."""
    existing = await db.execute(select(Hotel).where(Hotel.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hotel with slug '{data.slug}' already exists",
        )

    hotel = Hotel(**data.model_dump(), created_by=current_user.id)
    db.add(hotel)
    await db.commit()
    await db.refresh(hotel)
    return hotel


@router.get("/{hotel_id}", response_model=HotelResponse, dependencies=[RequireAdmin])
async def get_hotel(hotel_id: UUID, db: DatabaseSession):
    """Get hotel details."""
    result = await db.execute(
        select(Hotel).where(Hotel.id == hotel_id, Hotel.is_deleted == False)
    )
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    # Enrich hotel with calculated base price
    from app.services.hotel_service import HotelService
    service = HotelService(db)
    hotel = await service._enrich_hotel_with_base_price(hotel)
    return hotel


@router.put("/{hotel_id}", response_model=HotelResponse, dependencies=[RequireAdmin])
async def update_hotel(
    hotel_id: UUID,
    data: HotelUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update hotel."""
    result = await db.execute(
        select(Hotel).where(Hotel.id == hotel_id, Hotel.is_deleted == False)
    )
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    if data.slug and data.slug != hotel.slug:
        existing = await db.execute(
            select(Hotel).where(Hotel.slug == data.slug, Hotel.id != hotel_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hotel with slug '{data.slug}' already exists",
            )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(hotel, field, value)

    hotel.updated_by = current_user.id
    await db.commit()
    await db.refresh(hotel)
    return hotel


@router.delete("/{hotel_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_hotel(hotel_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft delete a hotel."""
    result = await db.execute(
        select(Hotel).where(Hotel.id == hotel_id, Hotel.is_deleted == False)
    )
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    hotel.is_deleted = True
    hotel.deleted_by = current_user.id
    await db.commit()
    return MessageResponse(message="Hotel deleted successfully")


# ============== FACILITIES & POLICIES ==============


@router.get("/{hotel_id}/facilities", response_model=dict, dependencies=[RequireAdmin])
async def get_hotel_facilities(hotel_id: UUID, db: DatabaseSession):
    """Get hotel facilities."""
    result = await db.execute(
        select(Hotel.facilities).where(Hotel.id == hotel_id, Hotel.is_deleted == False)
    )
    facilities = result.scalar()
    return facilities or {}


@router.put("/{hotel_id}/facilities", response_model=dict, dependencies=[RequireAdmin])
async def update_hotel_facilities(
    hotel_id: UUID, facilities: dict, current_user: CurrentUser, db: DatabaseSession
):
    """Update hotel facilities."""
    result = await db.execute(
        select(Hotel).where(Hotel.id == hotel_id, Hotel.is_deleted == False)
    )
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    hotel.facilities = facilities
    hotel.updated_by = current_user.id
    await db.commit()
    return hotel.facilities


@router.get("/{hotel_id}/policies", response_model=dict, dependencies=[RequireAdmin])
async def get_hotel_policies(hotel_id: UUID, db: DatabaseSession):
    """Get hotel policies."""
    result = await db.execute(
        select(Hotel.policies).where(Hotel.id == hotel_id, Hotel.is_deleted == False)
    )
    policies = result.scalar()
    return policies or {}


@router.put("/{hotel_id}/policies", response_model=dict, dependencies=[RequireAdmin])
async def update_hotel_policies(
    hotel_id: UUID, policies: dict, current_user: CurrentUser, db: DatabaseSession
):
    """Update hotel policies."""
    result = await db.execute(
        select(Hotel).where(Hotel.id == hotel_id, Hotel.is_deleted == False)
    )
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    hotel.policies = policies
    hotel.updated_by = current_user.id
    await db.commit()
    return hotel.policies


# ============== REVIEWS ==============


@router.get(
    "/{hotel_id}/reviews",
    response_model=PaginatedResponse[ReviewListItem],
    dependencies=[RequireAdmin],
)
async def list_hotel_reviews_admin(
    hotel_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_approved: Optional[bool] = None,
):
    """List all reviews for a hotel (admin)."""
    service = ReviewService(db)
    reviews, total = await service.admin_list(
        page=page,
        page_size=page_size,
        entity_type="hotel",
        entity_id=hotel_id,
        is_approved=is_approved,
    )
    
    return PaginatedResponse.create(reviews, total, page, page_size)


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


# ============== ROOM CRUD ==============


@router.get("/{hotel_id}/rooms", response_model=List[RoomResponse], dependencies=[RequireAdmin])
async def list_rooms(hotel_id: UUID, db: DatabaseSession):
    """List all rooms for a hotel."""
    # Verify hotel exists
    hotel_result = await db.execute(
        select(Hotel).where(Hotel.id == hotel_id, Hotel.is_deleted == False)
    )
    if not hotel_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Hotel not found")

    result = await db.execute(
        select(Room).where(Room.hotel_id == hotel_id, Room.is_deleted == False)
        .order_by(Room.room_type)
    )
    return list(result.scalars().all())


@router.post(
    "/{hotel_id}/rooms",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireAdmin],
)
async def create_room(
    hotel_id: UUID,
    data: RoomCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a room under a hotel."""
    hotel_result = await db.execute(
        select(Hotel).where(Hotel.id == hotel_id, Hotel.is_deleted == False)
    )
    if not hotel_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Hotel not found")

    room = Room(hotel_id=hotel_id, **data.model_dump(), created_by=current_user.id)
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


@router.put(
    "/{hotel_id}/rooms/{room_id}",
    response_model=RoomResponse,
    dependencies=[RequireAdmin],
)
async def update_room(
    hotel_id: UUID,
    room_id: UUID,
    data: RoomUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update a room."""
    result = await db.execute(
        select(Room).where(
            Room.id == room_id,
            Room.hotel_id == hotel_id,
            Room.is_deleted == False,
        )
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(room, field, value)

    room.updated_by = current_user.id
    await db.commit()
    await db.refresh(room)
    return room


@router.delete(
    "/{hotel_id}/rooms/{room_id}",
    response_model=MessageResponse,
    dependencies=[RequireAdmin],
)
async def delete_room(
    hotel_id: UUID,
    room_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Soft delete a room."""
    result = await db.execute(
        select(Room).where(
            Room.id == room_id,
            Room.hotel_id == hotel_id,
            Room.is_deleted == False,
        )
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    room.is_deleted = True
    room.deleted_by = current_user.id
    await db.commit()
    return MessageResponse(message="Room deleted successfully")
