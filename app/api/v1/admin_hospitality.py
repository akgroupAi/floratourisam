"""Admin endpoints for Hospitality Section management (Beyond Medical Care)."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.services.hospitality_service import HospitalityServiceManager
from app.schemas.hospitality import (
    HospitalityServiceCreate, HospitalityServiceUpdate, HospitalityServiceResponse,
    HospitalityPageCreate, HospitalityPageUpdate, HospitalityPageResponse,
)

router = APIRouter()


# ══════════════════════════════════════════════════
#  HOSPITALITY SERVICE CARDS (the 9-card grid)
# ══════════════════════════════════════════════════

@router.get(
    "/services",
    response_model=List[HospitalityServiceResponse],
    dependencies=[RequireAdmin],
    summary="List all hospitality service cards",
)
async def list_services(db: DatabaseSession):
    mgr = HospitalityServiceManager(db)
    return await mgr.list_services()


@router.post(
    "/services",
    response_model=HospitalityServiceResponse,
    dependencies=[RequireAdmin],
    summary="Create a hospitality service card",
)
async def create_service(body: HospitalityServiceCreate, db: DatabaseSession, user: CurrentUser):
    mgr = HospitalityServiceManager(db)
    # Check unique key
    existing = await mgr.get_service_by_key(body.key)
    if existing:
        raise HTTPException(400, f"Service with key '{body.key}' already exists")
    svc = await mgr.create_service(body.model_dump(), user.id)
    return svc


@router.get(
    "/services/{service_id}",
    response_model=HospitalityServiceResponse,
    dependencies=[RequireAdmin],
    summary="Get a hospitality service card",
)
async def get_service(service_id: UUID, db: DatabaseSession):
    mgr = HospitalityServiceManager(db)
    svc = await mgr.get_service(service_id)
    if not svc:
        raise HTTPException(404, "Hospitality service not found")
    return svc


@router.put(
    "/services/{service_id}",
    response_model=HospitalityServiceResponse,
    dependencies=[RequireAdmin],
    summary="Update a hospitality service card",
)
async def update_service(service_id: UUID, body: HospitalityServiceUpdate, db: DatabaseSession, user: CurrentUser):
    mgr = HospitalityServiceManager(db)
    svc = await mgr.update_service(service_id, body.model_dump(exclude_unset=True), user.id)
    if not svc:
        raise HTTPException(404, "Hospitality service not found")
    return svc


@router.delete(
    "/services/{service_id}",
    dependencies=[RequireAdmin],
    summary="Delete a hospitality service card",
)
async def delete_service(service_id: UUID, db: DatabaseSession, user: CurrentUser):
    mgr = HospitalityServiceManager(db)
    ok = await mgr.delete_service(service_id, user.id)
    if not ok:
        raise HTTPException(404, "Hospitality service not found")
    return {"message": "Hospitality service deleted successfully"}


# ══════════════════════════════════════════════════
#  HOSPITALITY PAGES (detail page per service)
# ══════════════════════════════════════════════════

@router.get(
    "/pages",
    response_model=List[HospitalityPageResponse],
    dependencies=[RequireAdmin],
    summary="List all hospitality detail pages",
)
async def list_pages(db: DatabaseSession):
    mgr = HospitalityServiceManager(db)
    return await mgr.list_pages()


@router.post(
    "/pages",
    response_model=HospitalityPageResponse,
    dependencies=[RequireAdmin],
    summary="Create a hospitality detail page",
)
async def create_page(body: HospitalityPageCreate, db: DatabaseSession, user: CurrentUser):
    mgr = HospitalityServiceManager(db)
    # Validate service exists
    svc = await mgr.get_service(body.service_id)
    if not svc:
        raise HTTPException(400, "Hospitality service not found")
    # Check slug uniqueness
    existing = await mgr.get_page_by_slug(body.slug)
    if existing:
        raise HTTPException(400, f"Page with slug '{body.slug}' already exists")
    page = await mgr.create_page(body.model_dump(), user.id)
    return page


@router.get(
    "/pages/{page_id}",
    response_model=HospitalityPageResponse,
    dependencies=[RequireAdmin],
    summary="Get a hospitality detail page",
)
async def get_page(page_id: UUID, db: DatabaseSession):
    mgr = HospitalityServiceManager(db)
    page = await mgr.get_page(page_id)
    if not page:
        raise HTTPException(404, "Hospitality page not found")
    return page


@router.put(
    "/pages/{page_id}",
    response_model=HospitalityPageResponse,
    dependencies=[RequireAdmin],
    summary="Update a hospitality detail page",
)
async def update_page(page_id: UUID, body: HospitalityPageUpdate, db: DatabaseSession, user: CurrentUser):
    mgr = HospitalityServiceManager(db)
    page = await mgr.update_page(page_id, body.model_dump(exclude_unset=True), user.id)
    if not page:
        raise HTTPException(404, "Hospitality page not found")
    return page


@router.delete(
    "/pages/{page_id}",
    dependencies=[RequireAdmin],
    summary="Delete a hospitality detail page",
)
async def delete_page(page_id: UUID, db: DatabaseSession, user: CurrentUser):
    mgr = HospitalityServiceManager(db)
    ok = await mgr.delete_page(page_id, user.id)
    if not ok:
        raise HTTPException(404, "Hospitality page not found")
    return {"message": "Hospitality page deleted successfully"}
