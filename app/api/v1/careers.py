"""Public Career endpoints — list active positions, view detail, apply."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DatabaseSession, OptionalUser
from app.schemas.career import (
    JobApplicationCreate,
    JobApplicationResponse,
    JobPositionListResponse,
    JobPositionResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.career_service import CareerService

router = APIRouter()


@router.get(
    "/positions",
    response_model=PaginatedResponse[JobPositionListResponse],
)
async def list_open_positions(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department: str | None = None,
    employment_type: str | None = None,
    location: str | None = None,
    search: str | None = None,
):
    """List active job positions (public)."""
    service = CareerService(db)
    items, total = await service.list_positions(
        page=page,
        page_size=page_size,
        active_only=True,
        department=department,
        employment_type=employment_type,
        location=location,
        search=search,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get("/positions/{slug}", response_model=JobPositionResponse)
async def get_position_by_slug(slug: str, db: DatabaseSession):
    """Get a job position detail by slug (public)."""
    service = CareerService(db)
    position = await service.get_position_by_slug(slug)
    if not position or not position.is_active:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


@router.get("/departments", response_model=list[str])
async def get_departments(db: DatabaseSession):
    """Get distinct departments (for filter dropdown)."""
    service = CareerService(db)
    return await service.get_departments()


@router.get("/locations", response_model=list[str])
async def get_locations(db: DatabaseSession):
    """Get distinct locations (for filter dropdown)."""
    service = CareerService(db)
    return await service.get_locations()


@router.post(
    "/apply",
    response_model=JobApplicationResponse,
    status_code=201,
)
async def apply_for_position(
    data: JobApplicationCreate,
    db: DatabaseSession,
    current_user: OptionalUser = None,
):
    """Submit a job application (public — auth optional)."""
    service = CareerService(db)
    user_id = current_user.id if current_user else None
    try:
        return await service.submit_application(data, user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
