"""Admin medical packages management endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.hospital import Department, Hospital
from app.schemas.booking import BookingListResponse, BookingResponse
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.package import (
    PackageCreate,
    PackageItemCreate,
    PackageItemResponse,
    PackageItemUpdate,
    PackageListResponse,
    PackageResponse,
    PackageUpdate,
)
from app.services.package_service import PackageService
from app.utils.enums import BookingType, PackageCategory

router = APIRouter()


def _enrich_list_response(package, hospital_name: Optional[str]) -> PackageListResponse:
    return PackageListResponse(
        id=package.id,
        name=package.name,
        slug=package.slug,
        short_description=package.short_description,
        category=package.category,
        price=package.price,
        discounted_price=package.discounted_price,
        discount_percentage=package.discount_percentage,
        currency=package.currency,
        duration_days=package.duration_days,
        image_url=package.image_url,
        is_featured=package.is_featured,
        hospital_id=package.hospital_id,
        hospital_name=hospital_name,
        created_at=package.created_at,
    )


# ============================================================
# Packages CRUD
# ============================================================

@router.get("", response_model=PaginatedResponse[PackageListResponse], dependencies=[RequireAdmin])
async def list_packages(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[PackageCategory] = Query(default=None),
    hospital_id: Optional[UUID] = Query(default=None),
    featured: Optional[bool] = Query(default=None),
    active: Optional[bool] = Query(default=None, description="Filter by is_active; omit for all"),
    search: Optional[str] = Query(default=None),
):
    """List all packages (including inactive) for admin management."""
    service = PackageService(db)
    packages, total = await service.get_list(
        pagination=PaginationParams(page=page, page_size=page_size),
        category=category,
        hospital_id=hospital_id,
        featured=featured,
        search=search,
        active_only=False if active is None else active,
    )

    hospital_ids = {p.hospital_id for p in packages if p.hospital_id}
    hospital_map: dict[UUID, str] = {}
    if hospital_ids:
        rows = await db.execute(
            select(Hospital.id, Hospital.name).where(Hospital.id.in_(hospital_ids))
        )
        hospital_map = {row.id: row.name for row in rows.all()}

    items = [_enrich_list_response(p, hospital_map.get(p.hospital_id)) for p in packages]
    return PaginatedResponse.create(items, total, page, page_size)


@router.post("", response_model=PackageResponse, status_code=status.HTTP_201_CREATED, dependencies=[RequireAdmin])
async def create_package(
    data: PackageCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a new medical package with optional items."""
    service = PackageService(db)
    try:
        package = await service.create(data, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return await _full_response(package, db)


@router.get("/{package_id}", response_model=PackageResponse, dependencies=[RequireAdmin])
async def get_package(package_id: UUID, db: DatabaseSession):
    """Get full package detail."""
    service = PackageService(db)
    package = await service.get_by_id(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    return await _full_response(package, db)


@router.put("/{package_id}", response_model=PackageResponse, dependencies=[RequireAdmin])
async def update_package(
    package_id: UUID,
    data: PackageUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update package metadata (does not touch items)."""
    service = PackageService(db)
    package = await service.get_by_id(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    try:
        package = await service.update(package, data, updated_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return await _full_response(package, db)


@router.delete("/{package_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_package(
    package_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Soft-delete a medical package."""
    service = PackageService(db)
    package = await service.get_by_id(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    await service.delete(package, deleted_by=current_user.id)
    return MessageResponse(message="Package deleted successfully")


# ============================================================
# Package items
# ============================================================

@router.post(
    "/{package_id}/items",
    response_model=PackageItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireAdmin],
)
async def add_package_item(
    package_id: UUID,
    data: PackageItemCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Add an item to an existing package."""
    service = PackageService(db)
    package = await service.get_by_id(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    item = await service.add_item(package, data, created_by=current_user.id)
    return PackageItemResponse(
        id=item.id,
        package_id=item.package_id,
        item_type=item.item_type,
        name=item.name,
        description=item.description,
        quantity=item.quantity,
        unit=item.unit,
        display_order=item.display_order,
        created_at=item.created_at,
    )


@router.put(
    "/{package_id}/items/{item_id}",
    response_model=PackageItemResponse,
    dependencies=[RequireAdmin],
)
async def update_package_item(
    package_id: UUID,
    item_id: UUID,
    data: PackageItemUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update a package item."""
    service = PackageService(db)
    item = await service.get_item_by_id(item_id)
    if not item or item.package_id != package_id:
        raise HTTPException(status_code=404, detail="Package item not found")
    item = await service.update_item(item, data, updated_by=current_user.id)
    return PackageItemResponse(
        id=item.id,
        package_id=item.package_id,
        item_type=item.item_type,
        name=item.name,
        description=item.description,
        quantity=item.quantity,
        unit=item.unit,
        display_order=item.display_order,
        created_at=item.created_at,
    )


@router.delete(
    "/{package_id}/items/{item_id}",
    response_model=MessageResponse,
    dependencies=[RequireAdmin],
)
async def remove_package_item(
    package_id: UUID,
    item_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Remove an item from a package (soft delete)."""
    service = PackageService(db)
    item = await service.get_item_by_id(item_id)
    if not item or item.package_id != package_id:
        raise HTTPException(status_code=404, detail="Package item not found")
    await service.remove_item(item, deleted_by=current_user.id)
    return MessageResponse(message="Package item removed successfully")


# ============================================================
# Package bookings (admin view)
# ============================================================

@router.get("/{package_id}/bookings", response_model=PaginatedResponse[BookingListResponse], dependencies=[RequireAdmin])
async def list_package_bookings(
    package_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all bookings for a specific package."""
    from app.models.booking import Booking
    from sqlalchemy import func

    service = PackageService(db)
    package = await service.get_by_id(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    base_q = (
        select(Booking)
        .where(
            Booking.package_id == package_id,
            Booking.booking_type == BookingType.PACKAGE.value,
            Booking.is_deleted == False,
        )
    )
    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    rows = await db.execute(
        base_q.order_by(Booking.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    bookings = list(rows.scalars().all())

    items = [
        BookingListResponse(
            id=b.id,
            reference_number=b.reference_number,
            booking_type=b.booking_type,
            status=b.status,
            booking_date=b.booking_date,
            guest_count=b.guest_count,
            total_price=b.total_price,
            currency=b.currency,
            is_paid=b.is_paid,
            created_at=b.created_at,
            entity_name=package.name,
        )
        for b in bookings
    ]
    return PaginatedResponse.create(items, total, page, page_size)


# ============================================================
# Internal helper
# ============================================================

async def _full_response(package, db) -> PackageResponse:
    """Build a full PackageResponse, enriching hospital/department names."""
    hospital_name: Optional[str] = None
    department_name: Optional[str] = None

    if package.hospital_id:
        row = (await db.execute(select(Hospital.name).where(Hospital.id == package.hospital_id))).one_or_none()
        hospital_name = row[0] if row else None

    if package.department_id:
        row = (await db.execute(select(Department.name).where(Department.id == package.department_id))).one_or_none()
        department_name = row[0] if row else None

    return PackageResponse(
        **{k: getattr(package, k) for k in PackageResponse.model_fields if hasattr(package, k)},
        hospital_name=hospital_name,
        department_name=department_name,
        discount_percentage=package.discount_percentage,
        items=[
            PackageItemResponse(
                id=item.id,
                package_id=item.package_id,
                item_type=item.item_type,
                name=item.name,
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                display_order=item.display_order,
                created_at=item.created_at,
            )
            for item in package.items
            if not item.is_deleted
        ],
    )
