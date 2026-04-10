"""Restaurant endpoints."""

from datetime import datetime, timedelta, timezone
from typing import List
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
async def list_restaurants(db: DatabaseSession, page: int = Query(1), page_size: int = Query(20), city: str = None):
    """List restaurants."""
    service = RestaurantService(db)
    restaurants, total = await service.get_list(PaginationParams(page=page, page_size=page_size), city)
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
