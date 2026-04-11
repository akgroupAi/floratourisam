"""Public apartment browsing endpoints.

Patients browse available apartments before booking via POST /bookings/apartment.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, DatabaseSession
from app.schemas.apartment import ApartmentResponse
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.review import (
    ReviewCreate,
    ReviewPublicResponse,
    ReviewResponse,
    ReviewSummary,
    SimpleReviewCreate,
)
from app.services.apartment_service import ApartmentService
from app.services.review_service import ReviewService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ApartmentResponse])
async def list_apartments(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    city: Optional[str] = Query(None),
    bedroom_type: Optional[str] = Query(None, description="studio | 1BR | 2BR | 3BR | 4BR+"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price per night"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price per night"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Minimum rating"),
    amenities: Optional[list[str]] = Query(None, description="Filter by amenities: wifi, ac, kitchen, washer, parking, pool, gym, balcony"),
    sort_by: Optional[str] = Query(
        "recommended",
        pattern="^(recommended|price_low_to_high|price_high_to_low|highest_rated|most_reviews)$",
        description="Sort order",
    ),
):
    """List apartments with filters and sorting."""
    service = ApartmentService(db)
    apartments, total = await service.get_list(
        PaginationParams(page=page, page_size=page_size),
        city=city,
        bedroom_type=bedroom_type,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        amenities=amenities,
        sort_by=sort_by,
    )
    return PaginatedResponse.create(apartments, total, page, page_size)


@router.get("/{apartment_id}", response_model=ApartmentResponse)
async def get_apartment(apartment_id: UUID, db: DatabaseSession):
    """Get apartment by ID."""
    service = ApartmentService(db)
    apartment = await service.get_by_id(apartment_id)
    if not apartment:
        raise HTTPException(status_code=404, detail="Apartment not found")
    return apartment


@router.get("/{apartment_id}/availability")
async def check_apartment_availability(
    apartment_id: UUID,
    db: DatabaseSession,
    check_in: date = Query(...),
    check_out: date = Query(...),
):
    """Check apartment availability for a date range."""
    if check_out <= check_in:
        raise HTTPException(status_code=400, detail="check_out must be after check_in")

    service = ApartmentService(db)
    available = await service.check_availability(
        apartment_id, str(check_in), str(check_out)
    )
    nights = (check_out - check_in).days
    return {
        "apartment_id": apartment_id,
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "available": available,
    }


# ============== REVIEWS ==============


@router.get(
    "/{apartment_id}/reviews", response_model=PaginatedResponse[ReviewPublicResponse]
)
async def list_apartment_reviews(
    apartment_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", description="created_at | rating | helpful_count"),
):
    """List approved reviews for an apartment."""
    service = ReviewService(db)
    reviews, total = await service.list_for_entity(
        entity_type="apartment",
        entity_id=apartment_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
    )
    return PaginatedResponse.create(reviews, total, page, page_size)


@router.get("/{apartment_id}/reviews/summary", response_model=ReviewSummary)
async def get_apartment_review_summary(apartment_id: UUID, db: DatabaseSession):
    """Get rating summary for an apartment."""
    service = ReviewService(db)
    return await service.get_entity_summary(entity_type="apartment", entity_id=apartment_id)


@router.post("/{apartment_id}/reviews", response_model=ReviewResponse)
async def submit_apartment_review(
    apartment_id: UUID,
    data: SimpleReviewCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Submit a review for an apartment. Only rating, title, and body are required."""
    review_data = ReviewCreate(
        entity_type="apartment",
        entity_id=apartment_id,
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
