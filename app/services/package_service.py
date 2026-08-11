"""Medical package service.

Handles CRUD for MedicalPackage / PackageItem and package booking creation.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.booking import Booking
from app.models.package import MedicalPackage, PackageItem
from app.schemas.package import (
    PackageBookingCreate,
    PackageCreate,
    PackageItemCreate,
    PackageItemUpdate,
    PackageUpdate,
)
from app.schemas.common import PaginationParams
from app.utils.enums import BookingStatus, BookingType, PackageCategory
from app.utils.helpers import generate_reference_id
from app.utils.pricing import price_with_platform_fee

logger = get_logger(__name__)


class PackageService:
    """Service for medical packages and package bookings."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_by_id(self, package_id: UUID) -> Optional[MedicalPackage]:
        result = await self.db.execute(
            select(MedicalPackage).where(
                MedicalPackage.id == package_id,
                MedicalPackage.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[MedicalPackage]:
        result = await self.db.execute(
            select(MedicalPackage).where(
                MedicalPackage.slug == slug,
                MedicalPackage.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        pagination: PaginationParams,
        category: Optional[PackageCategory] = None,
        hospital_id: Optional[UUID] = None,
        featured: Optional[bool] = None,
        search: Optional[str] = None,
        active_only: bool = True,
    ) -> tuple[List[MedicalPackage], int]:
        query = select(MedicalPackage).where(MedicalPackage.is_deleted == False)

        if active_only:
            query = query.where(MedicalPackage.is_active == True)
        if category:
            query = query.where(MedicalPackage.category == category.value)
        if hospital_id:
            query = query.where(MedicalPackage.hospital_id == hospital_id)
        if featured is not None:
            query = query.where(MedicalPackage.is_featured == featured)
        if search:
            query = query.where(MedicalPackage.name.ilike(f"%{search}%"))

        total_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = total_result.scalar() or 0

        query = (
            query.order_by(MedicalPackage.is_featured.desc(), MedicalPackage.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    # ------------------------------------------------------------------
    # Package CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        data: PackageCreate,
        created_by: Optional[UUID] = None,
    ) -> MedicalPackage:
        """Create a new medical package with optional items."""
        existing = await self.get_by_slug(data.slug)
        if existing:
            raise ValueError(f"A package with slug '{data.slug}' already exists")

        items_data = data.items or []
        package_data = data.model_dump(exclude={"items"})

        package = MedicalPackage(
            **{k: v for k, v in package_data.items() if v is not None or k in ("discounted_price",)},
            created_by=created_by,
        )
        # Explicitly set category value (enum → str)
        package.category = data.category.value if data.category else PackageCategory.GENERAL.value

        self.db.add(package)
        await self.db.flush()  # get package.id before inserting items

        for item_data in items_data:
            item = PackageItem(
                package_id=package.id,
                item_type=item_data.item_type.value,
                name=item_data.name,
                description=item_data.description,
                quantity=item_data.quantity,
                unit=item_data.unit,
                display_order=item_data.display_order,
                created_by=created_by,
            )
            self.db.add(item)

        await self.db.commit()
        await self.db.refresh(package)
        logger.info("package_created", package_id=str(package.id), slug=package.slug)
        return package

    async def update(
        self,
        package: MedicalPackage,
        data: PackageUpdate,
        updated_by: Optional[UUID] = None,
    ) -> MedicalPackage:
        """Update package fields (excludes items — use add/remove item methods)."""
        updates = data.model_dump(exclude_unset=True)

        if "slug" in updates and updates["slug"] != package.slug:
            existing = await self.get_by_slug(updates["slug"])
            if existing:
                raise ValueError(f"A package with slug '{updates['slug']}' already exists")

        if "category" in updates and updates["category"] is not None:
            updates["category"] = updates["category"].value

        for field, value in updates.items():
            setattr(package, field, value)

        package.updated_by = updated_by
        await self.db.commit()
        await self.db.refresh(package)
        logger.info("package_updated", package_id=str(package.id))
        return package

    async def delete(self, package: MedicalPackage, deleted_by: Optional[UUID] = None) -> None:
        """Soft-delete a package."""
        package.soft_delete(deleted_by=deleted_by)
        await self.db.commit()
        logger.info("package_deleted", package_id=str(package.id))

    # ------------------------------------------------------------------
    # Package items
    # ------------------------------------------------------------------

    async def add_item(
        self,
        package: MedicalPackage,
        data: PackageItemCreate,
        created_by: Optional[UUID] = None,
    ) -> PackageItem:
        item = PackageItem(
            package_id=package.id,
            item_type=data.item_type.value,
            name=data.name,
            description=data.description,
            quantity=data.quantity,
            unit=data.unit,
            display_order=data.display_order,
            created_by=created_by,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        logger.info("package_item_added", package_id=str(package.id), item_id=str(item.id))
        return item

    async def update_item(
        self,
        item: PackageItem,
        data: PackageItemUpdate,
        updated_by: Optional[UUID] = None,
    ) -> PackageItem:
        updates = data.model_dump(exclude_unset=True)
        if "item_type" in updates and updates["item_type"] is not None:
            updates["item_type"] = updates["item_type"].value
        for field, value in updates.items():
            setattr(item, field, value)
        item.updated_by = updated_by
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def get_item_by_id(self, item_id: UUID) -> Optional[PackageItem]:
        result = await self.db.execute(
            select(PackageItem).where(
                PackageItem.id == item_id,
                PackageItem.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def remove_item(
        self,
        item: PackageItem,
        deleted_by: Optional[UUID] = None,
    ) -> None:
        item.soft_delete(deleted_by=deleted_by)
        await self.db.commit()
        logger.info("package_item_removed", item_id=str(item.id))

    # ------------------------------------------------------------------
    # Package booking
    # ------------------------------------------------------------------

    async def book_package(
        self,
        patient_id: UUID,
        data: PackageBookingCreate,
        created_by: Optional[UUID] = None,
    ) -> Booking:
        """Create a booking for a medical package."""
        package = await self.get_by_id(data.package_id)
        if not package:
            raise ValueError("Package not found or no longer available")
        if not package.is_active:
            raise ValueError("This package is currently not available for booking")
        if data.guest_count > package.max_persons:
            raise ValueError(
                f"This package supports a maximum of {package.max_persons} person(s)"
            )

        effective_price = package.effective_price
        taxes = round(effective_price * 0.10, 2)
        _, platform_fee, total_price = price_with_platform_fee(effective_price, taxes)

        booking = Booking(
            patient_id=patient_id,
            booking_type=BookingType.PACKAGE.value,
            reference_number=generate_reference_id("PKG"),
            package_id=package.id,
            booking_date=datetime.now(timezone.utc),
            guest_count=data.guest_count,
            guest_details=data.guest_details,
            base_price=effective_price,
            taxes=taxes,
            discount=0.0,
            platform_fee=platform_fee,
            total_price=total_price,
            currency=package.currency,
            discount_code=data.discount_code,
            special_requests=data.special_requests,
            notes=data.notes,
            status=BookingStatus.CONFIRMED.value,
            confirmed_at=datetime.now(timezone.utc),
            confirmed_by=created_by,
            created_by=created_by,
            booking_metadata={
                "package_name": package.name,
                "package_slug": package.slug,
                "category": package.category,
                "duration_days": package.duration_days,
                "hospital_id": str(package.hospital_id) if package.hospital_id else None,
            },
        )

        self.db.add(booking)
        await self.db.commit()
        await self.db.refresh(booking)
        logger.info(
            "package_booked",
            booking_id=str(booking.id),
            ref=booking.reference_number,
            package_id=str(package.id),
            patient_id=str(patient_id),
        )
        return booking
