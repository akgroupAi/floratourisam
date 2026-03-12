"""Restaurant management endpoints for admin panel."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.restaurant import MealBooking, MenuCategory, MenuItem, Restaurant, Thali
from app.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter()


# ============== SCHEMAS ==============


class RestaurantCreate(BaseModel):
    """Schema for creating a restaurant."""

    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    cuisine_types: Optional[List[str]] = None
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
    opening_time: Optional[str] = None   # HH:MM format
    closing_time: Optional[str] = None
    operating_hours: Optional[dict] = None
    features: Optional[List[str]] = None
    dietary_options: Optional[List[str]] = None
    accepts_medical_diets: bool = False
    price_range: Optional[str] = None
    average_cost_per_person: Optional[float] = None
    currency: str = "USD"
    seating_capacity: Optional[int] = None
    accepts_reservations: bool = True
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    is_active: bool = True
    is_featured: bool = False


class RestaurantUpdate(BaseModel):
    """Schema for updating a restaurant."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    cuisine_types: Optional[List[str]] = None
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
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    operating_hours: Optional[dict] = None
    features: Optional[List[str]] = None
    dietary_options: Optional[List[str]] = None
    accepts_medical_diets: Optional[bool] = None
    price_range: Optional[str] = None
    average_cost_per_person: Optional[float] = None
    currency: Optional[str] = None
    seating_capacity: Optional[int] = None
    accepts_reservations: Optional[bool] = None
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_verified: Optional[bool] = None


class RestaurantResponse(BaseModel):
    """Schema for restaurant response."""

    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    cuisine_types: Optional[List[str]] = None
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
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    operating_hours: Optional[dict] = None
    features: Optional[List[str]] = None
    dietary_options: Optional[List[str]] = None
    accepts_medical_diets: bool = False
    price_range: Optional[str] = None
    average_cost_per_person: Optional[float] = None
    currency: str
    seating_capacity: Optional[int] = None
    accepts_reservations: bool = True
    rating: Optional[float] = None
    total_reviews: int = 0
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    is_active: bool
    is_featured: bool = False
    is_verified: bool = False

    class Config:
        from_attributes = True


# ---- Menu Category schemas ----

class MenuCategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    display_order: int = 0
    is_active: bool = True


class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class MenuCategoryResponse(BaseModel):
    id: UUID
    restaurant_id: UUID
    name: str
    description: Optional[str] = None
    display_order: int
    is_active: bool

    class Config:
        from_attributes = True


# ---- Menu Item schemas ----

class MenuItemCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    category: str = Field(..., description="Category label string (e.g. Appetizer, Main)")
    category_id: Optional[UUID] = None
    price: float = Field(..., gt=0)
    image_url: Optional[str] = None
    is_vegetarian: bool = False
    is_vegan: bool = False
    is_gluten_free: bool = False
    allergens: Optional[List[str]] = None
    calories: Optional[int] = None
    suitable_for_diabetics: bool = False
    low_sodium: bool = False
    medical_diet_notes: Optional[str] = None
    is_available: bool = True
    available_for: Optional[List[str]] = None
    is_featured: bool = False
    display_order: int = 0


class MenuItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    category_id: Optional[UUID] = None
    price: Optional[float] = Field(None, gt=0)
    image_url: Optional[str] = None
    is_vegetarian: Optional[bool] = None
    is_vegan: Optional[bool] = None
    is_gluten_free: Optional[bool] = None
    allergens: Optional[List[str]] = None
    calories: Optional[int] = None
    suitable_for_diabetics: Optional[bool] = None
    low_sodium: Optional[bool] = None
    medical_diet_notes: Optional[str] = None
    is_available: Optional[bool] = None
    available_for: Optional[List[str]] = None
    is_featured: Optional[bool] = None
    display_order: Optional[int] = None


class MenuItemResponse(BaseModel):
    id: UUID
    restaurant_id: UUID
    name: str
    description: Optional[str] = None
    category: str
    category_id: Optional[UUID] = None
    price: float
    image_url: Optional[str] = None
    is_vegetarian: bool
    is_vegan: bool
    is_gluten_free: bool
    allergens: Optional[List[str]] = None
    calories: Optional[int] = None
    suitable_for_diabetics: bool
    low_sodium: bool
    medical_diet_notes: Optional[str] = None
    is_available: bool
    available_for: Optional[List[str]] = None
    is_featured: bool
    display_order: int

    class Config:
        from_attributes = True


# ---- Thali schemas ----

class ThaliCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    image_url: Optional[str] = None
    menu_item_ids: Optional[List[str]] = None
    is_available: bool = True
    display_order: int = 0


class ThaliUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    image_url: Optional[str] = None
    menu_item_ids: Optional[List[str]] = None
    is_available: Optional[bool] = None
    display_order: Optional[int] = None


class ThaliResponse(BaseModel):
    id: UUID
    restaurant_id: UUID
    name: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    menu_item_ids: Optional[List[str]] = None
    is_available: bool
    display_order: int

    class Config:
        from_attributes = True


# ---- Order schemas ----

class OrderResponse(BaseModel):
    id: UUID
    restaurant_id: UUID
    meal_type: str
    booking_date: str
    booking_time: str
    guest_count: int
    status: str
    estimated_cost: Optional[float] = None
    contact_name: str
    contact_phone: str
    confirmation_code: Optional[str] = None

    class Config:
        from_attributes = True


# ============== RESTAURANT KPIs ==============


@router.get("/totals", dependencies=[RequireAdmin])
async def get_restaurant_totals(db: DatabaseSession):
    """Get restaurant KPI totals."""
    total = await db.execute(
        select(func.count(Restaurant.id)).where(Restaurant.is_deleted == False)
    )
    active = await db.execute(
        select(func.count(Restaurant.id)).where(
            Restaurant.is_deleted == False, Restaurant.is_active == True
        )
    )
    inactive = await db.execute(
        select(func.count(Restaurant.id)).where(
            Restaurant.is_deleted == False, Restaurant.is_active == False
        )
    )
    featured = await db.execute(
        select(func.count(Restaurant.id)).where(
            Restaurant.is_deleted == False, Restaurant.is_featured == True
        )
    )
    return {
        "total_restaurants": total.scalar() or 0,
        "active_restaurants": active.scalar() or 0,
        "inactive_restaurants": inactive.scalar() or 0,
        "featured_restaurants": featured.scalar() or 0,
    }


# ============== RESTAURANT CRUD ==============


@router.get("", response_model=PaginatedResponse[RestaurantResponse], dependencies=[RequireAdmin])
async def list_restaurants(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    city: Optional[str] = None,
    is_active: Optional[bool] = None,
    cuisine_type: Optional[str] = None,
):
    """List all restaurants with filtering."""
    query = select(Restaurant).where(Restaurant.is_deleted == False)

    if search:
        query = query.where(
            or_(
                Restaurant.name.ilike(f"%{search}%"),
                Restaurant.city.ilike(f"%{search}%"),
                Restaurant.email.ilike(f"%{search}%"),
            )
        )
    if city:
        query = query.where(Restaurant.city.ilike(f"%{city}%"))
    if is_active is not None:
        query = query.where(Restaurant.is_active == is_active)
    if cuisine_type:
        query = query.where(Restaurant.cuisine_types.any(cuisine_type))

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(Restaurant.name)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    restaurants = result.scalars().all()

    return PaginatedResponse.create(restaurants, total, page, page_size)


@router.post(
    "",
    response_model=RestaurantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireAdmin],
)
async def create_restaurant(
    data: RestaurantCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a new restaurant."""
    existing = await db.execute(
        select(Restaurant).where(Restaurant.slug == data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Restaurant with slug '{data.slug}' already exists",
        )

    # Convert time strings to time objects if provided
    payload = data.model_dump()
    for time_field in ("opening_time", "closing_time"):
        val = payload.get(time_field)
        if val:
            from datetime import time as dt_time
            h, m = val.split(":")
            payload[time_field] = dt_time(int(h), int(m))

    restaurant = Restaurant(**payload, created_by=current_user.id)
    db.add(restaurant)
    await db.commit()
    await db.refresh(restaurant)
    return restaurant


@router.get("/{restaurant_id}", response_model=RestaurantResponse, dependencies=[RequireAdmin])
async def get_restaurant(restaurant_id: UUID, db: DatabaseSession):
    """Get restaurant details."""
    result = await db.execute(
        select(Restaurant).where(
            Restaurant.id == restaurant_id, Restaurant.is_deleted == False
        )
    )
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


@router.put("/{restaurant_id}", response_model=RestaurantResponse, dependencies=[RequireAdmin])
async def update_restaurant(
    restaurant_id: UUID,
    data: RestaurantUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update restaurant."""
    result = await db.execute(
        select(Restaurant).where(
            Restaurant.id == restaurant_id, Restaurant.is_deleted == False
        )
    )
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    if data.slug and data.slug != restaurant.slug:
        existing = await db.execute(
            select(Restaurant).where(
                Restaurant.slug == data.slug, Restaurant.id != restaurant_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Restaurant with slug '{data.slug}' already exists",
            )

    payload = data.model_dump(exclude_unset=True)
    for time_field in ("opening_time", "closing_time"):
        val = payload.get(time_field)
        if val and isinstance(val, str):
            from datetime import time as dt_time
            h, m = val.split(":")
            payload[time_field] = dt_time(int(h), int(m))

    for field, value in payload.items():
        setattr(restaurant, field, value)

    restaurant.updated_by = current_user.id
    await db.commit()
    await db.refresh(restaurant)
    return restaurant


@router.delete("/{restaurant_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_restaurant(
    restaurant_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Soft delete a restaurant."""
    result = await db.execute(
        select(Restaurant).where(
            Restaurant.id == restaurant_id, Restaurant.is_deleted == False
        )
    )
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    restaurant.is_deleted = True
    restaurant.deleted_by = current_user.id
    await db.commit()
    return MessageResponse(message="Restaurant deleted successfully")


# ============== MENU CATEGORIES ==============


async def _get_restaurant_or_404(restaurant_id: UUID, db: DatabaseSession) -> Restaurant:
    result = await db.execute(
        select(Restaurant).where(
            Restaurant.id == restaurant_id, Restaurant.is_deleted == False
        )
    )
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


@router.get(
    "/{restaurant_id}/categories",
    response_model=List[MenuCategoryResponse],
    dependencies=[RequireAdmin],
)
async def list_menu_categories(restaurant_id: UUID, db: DatabaseSession):
    """List menu categories for a restaurant."""
    await _get_restaurant_or_404(restaurant_id, db)
    result = await db.execute(
        select(MenuCategory)
        .where(MenuCategory.restaurant_id == restaurant_id, MenuCategory.is_deleted == False)
        .order_by(MenuCategory.display_order, MenuCategory.name)
    )
    return list(result.scalars().all())


@router.post(
    "/{restaurant_id}/categories",
    response_model=MenuCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireAdmin],
)
async def create_menu_category(
    restaurant_id: UUID,
    data: MenuCategoryCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a menu category."""
    await _get_restaurant_or_404(restaurant_id, db)
    category = MenuCategory(
        restaurant_id=restaurant_id, **data.model_dump(), created_by=current_user.id
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.put(
    "/{restaurant_id}/categories/{category_id}",
    response_model=MenuCategoryResponse,
    dependencies=[RequireAdmin],
)
async def update_menu_category(
    restaurant_id: UUID,
    category_id: UUID,
    data: MenuCategoryUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update a menu category."""
    result = await db.execute(
        select(MenuCategory).where(
            MenuCategory.id == category_id,
            MenuCategory.restaurant_id == restaurant_id,
            MenuCategory.is_deleted == False,
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Menu category not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    category.updated_by = current_user.id
    await db.commit()
    await db.refresh(category)
    return category


@router.delete(
    "/{restaurant_id}/categories/{category_id}",
    response_model=MessageResponse,
    dependencies=[RequireAdmin],
)
async def delete_menu_category(
    restaurant_id: UUID,
    category_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Soft delete a menu category."""
    result = await db.execute(
        select(MenuCategory).where(
            MenuCategory.id == category_id,
            MenuCategory.restaurant_id == restaurant_id,
            MenuCategory.is_deleted == False,
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Menu category not found")

    category.is_deleted = True
    category.deleted_by = current_user.id
    await db.commit()
    return MessageResponse(message="Menu category deleted successfully")


# ============== MENU ITEMS ==============


@router.get(
    "/{restaurant_id}/menu",
    response_model=List[MenuItemResponse],
    dependencies=[RequireAdmin],
)
async def list_menu_items(
    restaurant_id: UUID,
    db: DatabaseSession,
    category_id: Optional[UUID] = None,
    is_available: Optional[bool] = None,
):
    """List menu items for a restaurant."""
    await _get_restaurant_or_404(restaurant_id, db)
    query = select(MenuItem).where(
        MenuItem.restaurant_id == restaurant_id, MenuItem.is_deleted == False
    )
    if category_id:
        query = query.where(MenuItem.category_id == category_id)
    if is_available is not None:
        query = query.where(MenuItem.is_available == is_available)
    query = query.order_by(MenuItem.category, MenuItem.display_order)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post(
    "/{restaurant_id}/menu",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireAdmin],
)
async def create_menu_item(
    restaurant_id: UUID,
    data: MenuItemCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a menu item."""
    await _get_restaurant_or_404(restaurant_id, db)
    item = MenuItem(
        restaurant_id=restaurant_id, **data.model_dump(), created_by=current_user.id
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.put(
    "/{restaurant_id}/menu/{item_id}",
    response_model=MenuItemResponse,
    dependencies=[RequireAdmin],
)
async def update_menu_item(
    restaurant_id: UUID,
    item_id: UUID,
    data: MenuItemUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update a menu item."""
    result = await db.execute(
        select(MenuItem).where(
            MenuItem.id == item_id,
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_deleted == False,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    item.updated_by = current_user.id
    await db.commit()
    await db.refresh(item)
    return item


@router.delete(
    "/{restaurant_id}/menu/{item_id}",
    response_model=MessageResponse,
    dependencies=[RequireAdmin],
)
async def delete_menu_item(
    restaurant_id: UUID,
    item_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Soft delete a menu item."""
    result = await db.execute(
        select(MenuItem).where(
            MenuItem.id == item_id,
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_deleted == False,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    item.is_deleted = True
    item.deleted_by = current_user.id
    await db.commit()
    return MessageResponse(message="Menu item deleted successfully")


# ============== THALIS ==============


@router.get(
    "/{restaurant_id}/thalis",
    response_model=List[ThaliResponse],
    dependencies=[RequireAdmin],
)
async def list_thalis(restaurant_id: UUID, db: DatabaseSession):
    """List thalis for a restaurant."""
    await _get_restaurant_or_404(restaurant_id, db)
    result = await db.execute(
        select(Thali).where(
            Thali.restaurant_id == restaurant_id, Thali.is_deleted == False
        ).order_by(Thali.display_order, Thali.name)
    )
    return list(result.scalars().all())


@router.post(
    "/{restaurant_id}/thalis",
    response_model=ThaliResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireAdmin],
)
async def create_thali(
    restaurant_id: UUID,
    data: ThaliCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a thali (fixed meal set)."""
    await _get_restaurant_or_404(restaurant_id, db)
    thali = Thali(
        restaurant_id=restaurant_id, **data.model_dump(), created_by=current_user.id
    )
    db.add(thali)
    await db.commit()
    await db.refresh(thali)
    return thali


@router.put(
    "/{restaurant_id}/thalis/{thali_id}",
    response_model=ThaliResponse,
    dependencies=[RequireAdmin],
)
async def update_thali(
    restaurant_id: UUID,
    thali_id: UUID,
    data: ThaliUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update a thali."""
    result = await db.execute(
        select(Thali).where(
            Thali.id == thali_id,
            Thali.restaurant_id == restaurant_id,
            Thali.is_deleted == False,
        )
    )
    thali = result.scalar_one_or_none()
    if not thali:
        raise HTTPException(status_code=404, detail="Thali not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(thali, field, value)

    thali.updated_by = current_user.id
    await db.commit()
    await db.refresh(thali)
    return thali


@router.delete(
    "/{restaurant_id}/thalis/{thali_id}",
    response_model=MessageResponse,
    dependencies=[RequireAdmin],
)
async def delete_thali(
    restaurant_id: UUID,
    thali_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Soft delete a thali."""
    result = await db.execute(
        select(Thali).where(
            Thali.id == thali_id,
            Thali.restaurant_id == restaurant_id,
            Thali.is_deleted == False,
        )
    )
    thali = result.scalar_one_or_none()
    if not thali:
        raise HTTPException(status_code=404, detail="Thali not found")

    thali.is_deleted = True
    thali.deleted_by = current_user.id
    await db.commit()
    return MessageResponse(message="Thali deleted successfully")


# ============== ORDERS (read-only) ==============


@router.get(
    "/{restaurant_id}/orders",
    response_model=PaginatedResponse[OrderResponse],
    dependencies=[RequireAdmin],
)
async def list_orders(
    restaurant_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List orders for a restaurant (read-only)."""
    await _get_restaurant_or_404(restaurant_id, db)
    query = select(MealBooking).where(MealBooking.restaurant_id == restaurant_id)
    if status_filter:
        query = query.where(MealBooking.status == status_filter)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    query = query.order_by(MealBooking.booking_date.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    orders = result.scalars().all()

    # Serialize time fields manually
    items = []
    for o in orders:
        items.append(
            OrderResponse(
                id=o.id,
                restaurant_id=o.restaurant_id,
                meal_type=o.meal_type,
                booking_date=str(o.booking_date),
                booking_time=str(o.booking_time),
                guest_count=o.guest_count,
                status=o.status,
                estimated_cost=o.estimated_cost,
                contact_name=o.contact_name,
                contact_phone=o.contact_phone,
                confirmation_code=o.confirmation_code,
            )
        )

    return PaginatedResponse.create(items, total, page, page_size)
