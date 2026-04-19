"""Service layer for Hospitality Section CRUD."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hospitality import HospitalityService, HospitalityPage


class HospitalityServiceManager:
    """CRUD for HospitalityService (grid cards) and HospitalityPage (detail pages)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Service cards ─────────────────────────────────────

    async def list_services(self, *, active_only: bool = False) -> list[HospitalityService]:
        q = (
            select(HospitalityService)
            .where(HospitalityService.is_deleted == False)
            .options(selectinload(HospitalityService.page))
            .order_by(HospitalityService.display_order)
        )
        if active_only:
            q = q.where(HospitalityService.is_active == True)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_service(self, service_id: UUID) -> Optional[HospitalityService]:
        result = await self.db.execute(
            select(HospitalityService)
            .where(HospitalityService.id == service_id, HospitalityService.is_deleted == False)
            .options(selectinload(HospitalityService.page))
        )
        return result.scalar_one_or_none()

    async def get_service_by_key(self, key: str) -> Optional[HospitalityService]:
        result = await self.db.execute(
            select(HospitalityService)
            .where(HospitalityService.key == key, HospitalityService.is_deleted == False)
            .options(selectinload(HospitalityService.page))
        )
        return result.scalar_one_or_none()

    async def create_service(self, data: dict, user_id: UUID) -> HospitalityService:
        svc = HospitalityService(**data, created_by=user_id)
        self.db.add(svc)
        await self.db.flush()
        return await self.get_service(svc.id)

    async def update_service(self, service_id: UUID, data: dict, user_id: UUID) -> Optional[HospitalityService]:
        svc = await self.get_service(service_id)
        if not svc:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(svc, k, v)
        svc.updated_by = user_id
        await self.db.flush()
        return await self.get_service(service_id)

    async def delete_service(self, service_id: UUID, user_id: UUID) -> bool:
        svc = await self.get_service(service_id)
        if not svc:
            return False
        svc.soft_delete(deleted_by=user_id)
        await self.db.flush()
        return True

    # ── Detail pages ──────────────────────────────────────

    async def list_pages(self, *, active_only: bool = False) -> list[HospitalityPage]:
        q = (
            select(HospitalityPage)
            .where(HospitalityPage.is_deleted == False)
            .options(selectinload(HospitalityPage.service))
        )
        if active_only:
            q = q.where(HospitalityPage.is_active == True)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_page(self, page_id: UUID) -> Optional[HospitalityPage]:
        result = await self.db.execute(
            select(HospitalityPage)
            .where(HospitalityPage.id == page_id, HospitalityPage.is_deleted == False)
            .options(selectinload(HospitalityPage.service))
        )
        return result.scalar_one_or_none()

    async def get_page_by_slug(self, slug: str) -> Optional[HospitalityPage]:
        result = await self.db.execute(
            select(HospitalityPage)
            .where(HospitalityPage.slug == slug, HospitalityPage.is_deleted == False, HospitalityPage.is_active == True)
            .options(selectinload(HospitalityPage.service))
        )
        return result.scalar_one_or_none()

    async def create_page(self, data: dict, user_id: UUID) -> HospitalityPage:
        page = HospitalityPage(**data, created_by=user_id)
        self.db.add(page)
        await self.db.flush()
        return await self.get_page(page.id)

    async def update_page(self, page_id: UUID, data: dict, user_id: UUID) -> Optional[HospitalityPage]:
        page = await self.get_page(page_id)
        if not page:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(page, k, v)
        page.updated_by = user_id
        await self.db.flush()
        return await self.get_page(page_id)

    async def delete_page(self, page_id: UUID, user_id: UUID) -> bool:
        page = await self.get_page(page_id)
        if not page:
            return False
        page.soft_delete(deleted_by=user_id)
        await self.db.flush()
        return True
