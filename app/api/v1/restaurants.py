"""Restaurant endpoints."""

from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DatabaseSession
from app.models.booking import Booking
from app.models.restaurant import DiningPass, DiningPassPurchase, MenuCategory, Restaurant
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.restaurant import (
    RestaurantResponse,
    MenuItemResponse,
    MenuCategoryResponse,
    MenuCategoryWithItems,
    RestaurantMinimalResponse,
    DiningPassResponse,
)
from app.services.patient_service import PatientService
from app.services.restaurant_service import RestaurantService
from app.utils.enums import BookingStatus, BookingType
from app.utils.helpers import generate_reference_id

router = APIRouter()


# ============== SCHEMAS ==============


class PurchasePassRequest(BaseModel):
    dining_pass_id: UUID
    start_date: Optional[date] = Field(None, description="When the pass should start. Defaults to today if not provided.")


class PurchasePassResponse(BaseModel):
    id: UUID
    reference_code: str
    qr_data: str
    pass_name: str
    restaurant_id: UUID
    restaurant_name: Optional[str] = None
    tokens_total: int
    tokens_used: int
    tokens_remaining: int
    percentage_used: float
    purchased_at: str
    expires_at: str
    days_left: int
    amount_paid: float
    currency: str
    status: str
    booking_id: Optional[UUID] = None

    class Config:
        from_attributes = True


# ============== HELPERS ==============


def _build_pass_response(p: DiningPassPurchase, restaurant_name: Optional[str] = None) -> PurchasePassResponse:
    """Build a PurchasePassResponse from a DiningPassPurchase model."""
    now = datetime.now(timezone.utc)
    expires = p.expires_at.replace(tzinfo=timezone.utc) if p.expires_at.tzinfo is None else p.expires_at
    days_left = max(0, (expires - now).days)
    tokens_remaining = p.tokens_total - p.tokens_used
    pct_used = round((p.tokens_used / p.tokens_total) * 100, 1) if p.tokens_total > 0 else 0.0

    # QR data: JSON string that admin scanner can parse
    qr_data = f'{{"ref":"{p.reference_code}","restaurant_id":"{p.restaurant_id}"}}'

    return PurchasePassResponse(
        id=p.id,
        reference_code=p.reference_code,
        qr_data=qr_data,
        pass_name=p.pass_name,
        restaurant_id=p.restaurant_id,
        restaurant_name=restaurant_name or (p.restaurant.name if hasattr(p, "restaurant") and p.restaurant else None),
        tokens_total=p.tokens_total,
        tokens_used=p.tokens_used,
        tokens_remaining=tokens_remaining,
        percentage_used=pct_used,
        purchased_at=str(p.purchased_at),
        expires_at=str(p.expires_at),
        days_left=days_left,
        amount_paid=p.amount_paid,
        currency=p.currency,
        status=p.status,
    )


# ============== ENDPOINTS ==============


@router.get("/all", response_model=list[RestaurantMinimalResponse])
async def list_all_restaurants_minimal(db: DatabaseSession):
    """List all restaurants minimal."""
    service = RestaurantService(db)
    return await service.get_list_minimal()

@router.get("", response_model=PaginatedResponse[RestaurantResponse])
async def list_restaurants(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    city: Optional[str] = Query(None),
    cuisine_type: Optional[str] = Query(None, description="Filter by cuisine type"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Minimum rating: 3, 3.5, 4, 4.5"),
    dietary_options: Optional[list[str]] = Query(None, description="Filter by dietary options: vegetarian, vegan, gluten_free, jain, organic, halal"),
    price_range: Optional[str] = Query(None, pattern="^(\\$|\\$\\$|\\$\\$\\$|\\$\\$\\$\\$)$", description="Price range: $, $$, $$$, $$$$"),
    sort_by: Optional[str] = Query("recommended", pattern="^(recommended|highest_rated|most_reviews|nearest_first)$", description="Sort order"),
    user_lat: Optional[float] = Query(None, description="User latitude for nearest_first sort"),
    user_lng: Optional[float] = Query(None, description="User longitude for nearest_first sort"),
):
    """List restaurants with filters and sorting."""
    service = RestaurantService(db)
    restaurants, total = await service.get_list(
        PaginationParams(page=page, page_size=page_size),
        city=city,
        cuisine_type=cuisine_type,
        min_rating=min_rating,
        dietary_options=dietary_options,
        price_range=price_range,
        sort_by=sort_by,
        user_lat=user_lat,
        user_lng=user_lng,
    )
    return PaginatedResponse.create(restaurants, total, page, page_size)


@router.get(
    "/me/dining-passes",
    response_model=List[PurchasePassResponse],
)
async def get_my_dining_passes(
    current_user: CurrentUser,
    db: DatabaseSession,
    status_filter: Optional[str] = Query(None, pattern="^(pending|active|expired|fully_used|cancelled)$", description="Filter by pass status"),
):
    """Get all dining passes purchased by the current user with QR data."""
    query = (
        select(DiningPassPurchase)
        .options(selectinload(DiningPassPurchase.restaurant))
        .where(
            DiningPassPurchase.user_id == current_user.id,
            DiningPassPurchase.is_deleted == False,
        )
    )

    if status_filter:
        query = query.where(DiningPassPurchase.status == status_filter)

    query = query.order_by(DiningPassPurchase.purchased_at.desc())
    result = await db.execute(query)
    purchases = result.scalars().all()

    # Auto-expire passes that are past expiry date
    now = datetime.now(timezone.utc)
    for p in purchases:
        expires = p.expires_at.replace(tzinfo=timezone.utc) if p.expires_at.tzinfo is None else p.expires_at
        if p.status == "active" and now > expires:
            p.status = "expired"
    await db.commit()

    return [_build_pass_response(p) for p in purchases]


@router.get("/{restaurant_id}", response_model=RestaurantResponse)
async def get_restaurant(restaurant_id: UUID, db: DatabaseSession):
    """Get restaurant by ID."""
    service = RestaurantService(db)
    restaurant = await service.get_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


@router.get("/{restaurant_id}/menu", response_model=list[MenuItemResponse])
async def get_restaurant_menu(restaurant_id: UUID, db: DatabaseSession):
    """Get restaurant menu."""
    service = RestaurantService(db)
    return await service.get_menu(restaurant_id)


@router.get("/{restaurant_id}/menu/grouped", response_model=list[MenuCategoryWithItems])
async def get_restaurant_menu_grouped(restaurant_id: UUID, db: DatabaseSession):
    """Get restaurant menu grouped by category with items."""
    from app.models.restaurant import MenuItem, MenuCategory as MenuCategoryModel
    from collections import OrderedDict

    # Get categories
    cat_result = await db.execute(
        select(MenuCategoryModel).where(
            MenuCategoryModel.restaurant_id == restaurant_id,
            MenuCategoryModel.is_active == True,
            MenuCategoryModel.is_deleted == False,
        ).order_by(MenuCategoryModel.display_order)
    )
    categories = list(cat_result.scalars().all())

    # Get available menu items
    item_result = await db.execute(
        select(MenuItem).where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_available == True,
            MenuItem.is_deleted == False,
        ).order_by(MenuItem.display_order)
    )
    items = list(item_result.scalars().all())

    # Build category map
    grouped = OrderedDict()
    for cat in categories:
        grouped[cat.id] = {
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "display_order": cat.display_order,
            "items": [],
        }

    # Assign items to categories
    uncategorized_items = []
    for item in items:
        if item.category_id and item.category_id in grouped:
            grouped[item.category_id]["items"].append(item)
        else:
            uncategorized_items.append(item)

    result = list(grouped.values())

    # Add uncategorized items under a generic group
    if uncategorized_items:
        from uuid import uuid4
        result.append({
            "id": uuid4(),
            "name": "Other",
            "description": None,
            "display_order": 9999,
            "items": uncategorized_items,
        })

    return result


@router.get("/{restaurant_id}/menu/highlights", response_model=list[MenuItemResponse])
async def get_menu_highlights(restaurant_id: UUID, db: DatabaseSession):
    """Get featured/highlighted menu items (chef's curated selection)."""
    from app.models.restaurant import MenuItem

    result = await db.execute(
        select(MenuItem).where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_available == True,
            MenuItem.is_deleted == False,
            MenuItem.is_featured == True,
        ).order_by(MenuItem.display_order)
    )
    return list(result.scalars().all())


@router.get("/{restaurant_id}/categories", response_model=list[MenuCategoryResponse])
async def get_restaurant_categories(restaurant_id: UUID, db: DatabaseSession):
    """Get restaurant menu categories."""
    result = await db.execute(
        select(MenuCategory).where(
            MenuCategory.restaurant_id == restaurant_id,
            MenuCategory.is_active == True,
            MenuCategory.is_deleted == False,
        ).order_by(MenuCategory.display_order)
    )
    return list(result.scalars().all())


@router.get("/{restaurant_id}/dining-passes", response_model=list[DiningPassResponse])
async def get_restaurant_dining_passes(restaurant_id: UUID, db: DatabaseSession):
    """Get available dining passes for a restaurant."""
    result = await db.execute(
        select(DiningPass).where(
            DiningPass.restaurant_id == restaurant_id,
            DiningPass.is_active == True,
            DiningPass.is_deleted == False,
        )
    )
    return list(result.scalars().all())


@router.post(
    "/{restaurant_id}/dining-passes/purchase",
    response_model=PurchasePassResponse,
    status_code=status.HTTP_201_CREATED,
)
async def purchase_dining_pass(
    restaurant_id: UUID,
    data: PurchasePassRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Purchase a dining pass for a restaurant.

    Creates a pending DiningPassPurchase and a Booking record.
    The frontend should then call POST /api/v1/payments/stripe/checkout
    with the returned booking_id and amount to initiate Stripe payment.
    The pass activates automatically when the Stripe webhook confirms payment.
    """
    result = await db.execute(
        select(DiningPass).where(
            DiningPass.id == data.dining_pass_id,
            DiningPass.restaurant_id == restaurant_id,
            DiningPass.is_active == True,
            DiningPass.is_deleted == False,
        )
    )
    dining_pass = result.scalar_one_or_none()
    if not dining_pass:
        raise HTTPException(status_code=404, detail="Dining pass not found")

    # Check date-based availability
    today = datetime.now(timezone.utc).date()
    if dining_pass.available_from and today < dining_pass.available_from:
        raise HTTPException(status_code=400, detail="This dining pass is not available yet")
    if dining_pass.available_until and today > dining_pass.available_until:
        raise HTTPException(status_code=400, detail="This dining pass is no longer available")

    # Get restaurant name
    rest_result = await db.execute(
        select(Restaurant.name).where(Restaurant.id == restaurant_id)
    )
    restaurant_name = rest_result.scalar_one_or_none() or ""

    now = datetime.now(timezone.utc)

    # Use user-selected start_date or default to now
    if data.start_date:
        start_dt = datetime.combine(data.start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        if start_dt.date() < now.date():
            raise HTTPException(status_code=400, detail="Start date cannot be in the past")
    else:
        start_dt = now

    expires_at = start_dt + timedelta(days=dining_pass.duration_days)

    # Get or create patient profile for the user
    patient_service = PatientService(db)
    patient = await patient_service.get_or_create(current_user.id)

    # Create Booking record for payment tracking
    booking = Booking(
        patient_id=patient.id,
        booking_type=BookingType.RESTAURANT.value,
        reference_number=generate_reference_id("BKG"),
        restaurant_id=restaurant_id,
        status=BookingStatus.PENDING.value,
        booking_date=now,
        base_price=dining_pass.price,
        total_price=dining_pass.price,
        currency=dining_pass.currency,
        source="website",
        booking_metadata={
            "type": "dining_pass",
            "dining_pass_id": str(dining_pass.id),
            "dining_pass_name": dining_pass.name,
        },
        created_by=current_user.id,
    )
    db.add(booking)
    await db.flush()  # Get booking.id before creating purchase

    # Create DiningPassPurchase in pending state
    purchase = DiningPassPurchase(
        dining_pass_id=dining_pass.id,
        user_id=current_user.id,
        restaurant_id=restaurant_id,
        pass_name=dining_pass.name,
        reference_code=generate_reference_id("FLR"),
        tokens_total=dining_pass.tokens,
        tokens_used=0,
        purchased_at=start_dt,
        expires_at=expires_at,
        amount_paid=dining_pass.price,
        currency=dining_pass.currency,
        status="pending",
        booking_id=booking.id,
        created_by=current_user.id,
    )
    db.add(purchase)

    # Store purchase ID in booking metadata for webhook lookup
    booking.booking_metadata["dining_pass_purchase_id"] = str(purchase.id)

    await db.commit()
    await db.refresh(purchase)

    response = _build_pass_response(purchase, restaurant_name=restaurant_name)
    response.booking_id = booking.id
    return response


@router.get(
    "/{restaurant_id}/pass-verify/{reference_code}",
    response_model=PurchasePassResponse,
)
async def verify_pass_by_qr(
    restaurant_id: UUID,
    reference_code: str,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Verify a dining pass by reference code (QR scan). Returns pass details and validity."""
    result = await db.execute(
        select(DiningPassPurchase)
        .options(selectinload(DiningPassPurchase.restaurant))
        .where(
            DiningPassPurchase.reference_code == reference_code,
            DiningPassPurchase.restaurant_id == restaurant_id,
            DiningPassPurchase.is_deleted == False,
        )
    )
    purchase = result.scalar_one_or_none()
    if not purchase:
        raise HTTPException(status_code=404, detail="Pass not found for this restaurant")

    # Auto-expire if past expiry
    now = datetime.now(timezone.utc)
    expires = purchase.expires_at.replace(tzinfo=timezone.utc) if purchase.expires_at.tzinfo is None else purchase.expires_at
    if purchase.status == "active" and now > expires:
        purchase.status = "expired"
        await db.commit()

    return _build_pass_response(purchase)
