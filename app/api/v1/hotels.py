"""Hotel endpoints."""

from datetime import date
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from app.api.deps import DatabaseSession
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.hotel import HotelResponse, RoomResponse
from app.schemas.review import (
    ReviewCreate,
    ReviewListItem,
    ReviewPaginatedResponse,
    ReviewPublicResponse,
    ReviewResponse,
    ReviewSummary,
    SimpleReviewCreate,
)
from app.services.hotel_service import HotelService
from app.services.review_service import ReviewService
from app.api.deps import CurrentUser

router = APIRouter()


@router.get("", response_model=PaginatedResponse[HotelResponse])
async def list_hotels(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by hotel name, description, or city"),
    city: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price per night"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price per night"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Minimum rating (e.g. 3, 3.5, 4, 4.5)"),
    amenities: Optional[list[str]] = Query(None, description="Filter by amenities: wifi, pool, spa, gym, restaurant, kitchen, medical_support"),
    sort_by: Optional[str] = Query("recommended", pattern="^(recommended|price_low_to_high|price_high_to_low|highest_rated|most_reviews)$", description="Sort order"),
):
    """List hotels with filters and sorting."""
    service = HotelService(db)
    hotels, total = await service.get_list(
        PaginationParams(page=page, page_size=page_size),
        search=search,
        city=city,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        amenities=amenities,
        sort_by=sort_by,
    )
    return PaginatedResponse.create(hotels, total, page, page_size)


@router.get("/{hotel_id}", response_model=HotelResponse)
async def get_hotel(hotel_id: UUID, db: DatabaseSession):
    """Get hotel by ID."""
    service = HotelService(db)
    hotel = await service.get_by_id(hotel_id)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    # Enrich hotel with calculated base price
    hotel = await service._enrich_hotel_with_base_price(hotel)
    return hotel


@router.get("/{hotel_id}/facilities", response_model=dict)
async def get_hotel_facilities(hotel_id: UUID, db: DatabaseSession):
    """Get hotel facilities (public)."""
    result = await db.execute(
        select(Hotel.facilities).where(Hotel.id == hotel_id, Hotel.is_active == True)
    )
    facilities = result.scalar()
    return facilities or {}


@router.get("/{hotel_id}/policies", response_model=dict)
async def get_hotel_policies(hotel_id: UUID, db: DatabaseSession):
    """Get hotel policies (public)."""
    result = await db.execute(
        select(Hotel.policies).where(Hotel.id == hotel_id, Hotel.is_active == True)
    )
    policies = result.scalar()
    return policies or {}


@router.get("/{hotel_id}/rooms", response_model=list[RoomResponse])
async def get_hotel_rooms(hotel_id: UUID, db: DatabaseSession):
    """Get hotel rooms."""
    service = HotelService(db)
    return await service.get_rooms(hotel_id)


@router.get("/{hotel_id}/rooms/{room_id}/availability")
async def check_room_availability(
    hotel_id: UUID,
    room_id: UUID,
    db: DatabaseSession,
    check_in: date = Query(..., description="Check-in date (YYYY-MM-DD)"),
    check_out: date = Query(..., description="Check-out date (YYYY-MM-DD)"),
):
    """Check whether this room type has a unit free for the given dates."""
    service = HotelService(db)
    try:
        available = await service.check_availability(room_id, check_in, check_out)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "room_id": room_id,
        "check_in": check_in,
        "check_out": check_out,
        "nights": (check_out - check_in).days,
        "available": available,
    }


# ============== REVIEWS ==============


@router.get(
    "/{hotel_id}/reviews", response_model=ReviewPaginatedResponse
)
async def list_hotel_reviews(
    hotel_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", description="created_at | rating | helpful_count"),
):
    """List approved reviews for a hotel."""
    service = ReviewService(db)
    reviews, total, average_rating = await service.list_for_entity(
        entity_type="hotel",
        entity_id=hotel_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
    )
    return ReviewPaginatedResponse.create(reviews, total, page, page_size, average_rating)


@router.get("/{hotel_id}/reviews/summary", response_model=ReviewSummary)
async def get_hotel_review_summary(hotel_id: UUID, db: DatabaseSession):
    """Get rating summary for a hotel."""
    service = ReviewService(db)
    return await service.get_entity_summary(entity_type="hotel", entity_id=hotel_id)


@router.post("/{hotel_id}/reviews", response_model=ReviewResponse)
async def submit_hotel_review(
    hotel_id: UUID,
    data: SimpleReviewCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Submit a review for a hotel. Only rating, title, and body are required in the body."""
    review_data = ReviewCreate(
        entity_type="hotel",
        entity_id=hotel_id,
        rating=data.rating,
        title=data.title,
        body=data.body,
    )

    service = ReviewService(db)
    try:
        return await service.submit_review(
            user_id=current_user.id, data=review_data, created_by=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
