"""Restaurant endpoints."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DatabaseSession
from app.models.restaurant import DiningPass, DiningPassPurchase, MenuCategory
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.restaurant import (
    RestaurantResponse,
    MenuItemResponse,
    MenuCategoryResponse,
    MenuCategoryWithItems,
    RestaurantMinimalResponse,
    DiningPassResponse,
)
from app.services.restaurant_service import RestaurantService
from app.utils.helpers import generate_reference_id

router = APIRouter()


# ============== SCHEMAS ==============


class PurchasePassRequest(BaseModel):
    dining_pass_id: UUID


class PurchasePassResponse(BaseModel):
    id: UUID
    reference_code: str
    pass_name: str
    restaurant_id: UUID
    tokens_total: int
    tokens_used: int
    tokens_remaining: int
    purchased_at: str
    expires_at: str
    amount_paid: float
    currency: str
    status: str

    class Config:
        from_attributes = True


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
):
    """Get all dining passes purchased by the current user."""
    result = await db.execute(
        select(DiningPassPurchase).where(
            DiningPassPurchase.user_id == current_user.id,
            DiningPassPurchase.is_deleted == False,
        ).order_by(DiningPassPurchase.purchased_at.desc())
    )
    purchases = result.scalars().all()

    return [
        PurchasePassResponse(
            id=p.id,
            reference_code=p.reference_code,
            pass_name=p.pass_name,
            restaurant_id=p.restaurant_id,
            tokens_total=p.tokens_total,
            tokens_used=p.tokens_used,
            tokens_remaining=p.tokens_total - p.tokens_used,
            purchased_at=str(p.purchased_at),
            expires_at=str(p.expires_at),
            amount_paid=p.amount_paid,
            currency=p.currency,
            status=p.status,
        )
        for p in purchases
    ]


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
    """Purchase a dining pass for a restaurant."""
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

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=dining_pass.duration_days)

    purchase = DiningPassPurchase(
        dining_pass_id=dining_pass.id,
        user_id=current_user.id,
        restaurant_id=restaurant_id,
        pass_name=dining_pass.name,
        reference_code=generate_reference_id("DPP"),
        tokens_total=dining_pass.tokens,
        tokens_used=0,
        purchased_at=now,
        expires_at=expires_at,
        amount_paid=dining_pass.price,
        currency=dining_pass.currency,
        status="active",
        created_by=current_user.id,
    )
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase)

    return PurchasePassResponse(
        id=purchase.id,
        reference_code=purchase.reference_code,
        pass_name=purchase.pass_name,
        restaurant_id=purchase.restaurant_id,
        tokens_total=purchase.tokens_total,
        tokens_used=purchase.tokens_used,
        tokens_remaining=purchase.tokens_total - purchase.tokens_used,
        purchased_at=str(purchase.purchased_at),
        expires_at=str(purchase.expires_at),
        amount_paid=purchase.amount_paid,
        currency=purchase.currency,
        status=purchase.status,
    )
