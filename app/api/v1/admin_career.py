"""Admin — Career / Job Position management."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.career import (
    JobApplicationListResponse,
    JobApplicationResponse,
    JobApplicationStatusUpdate,
    JobPositionCreate,
    JobPositionResponse,
    JobPositionUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services.career_service import CareerService

router = APIRouter()


# ── Job Positions CRUD ────────────────────────────────────────


@router.post(
    "/positions",
    response_model=JobPositionResponse,
    status_code=201,
    dependencies=[RequireAdmin],
)
async def create_position(
    data: JobPositionCreate,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    """Create a new job position."""
    service = CareerService(db)
    return await service.create_position(data, created_by=current_user.id)


@router.put(
    "/positions/{position_id}",
    response_model=JobPositionResponse,
    dependencies=[RequireAdmin],
)
async def update_position(
    position_id: UUID,
    data: JobPositionUpdate,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    """Update a job position."""
    service = CareerService(db)
    try:
        return await service.update_position(position_id, data, updated_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/positions/{position_id}",
    status_code=204,
    dependencies=[RequireAdmin],
)
async def delete_position(
    position_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    """Soft-delete a job position."""
    service = CareerService(db)
    try:
        await service.delete_position(position_id, deleted_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/positions/{position_id}",
    response_model=JobPositionResponse,
    dependencies=[RequireAdmin],
)
async def get_position(position_id: UUID, db: DatabaseSession):
    """Get a single job position (admin view)."""
    service = CareerService(db)
    position = await service.get_position(position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


@router.get(
    "/positions",
    response_model=PaginatedResponse[JobPositionResponse],
    dependencies=[RequireAdmin],
)
async def list_positions(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department: str | None = None,
    employment_type: str | None = None,
    location: str | None = None,
    search: str | None = None,
):
    """List all job positions (admin — includes inactive)."""
    service = CareerService(db)
    items, total = await service.list_positions(
        page=page,
        page_size=page_size,
        active_only=False,
        department=department,
        employment_type=employment_type,
        location=location,
        search=search,
    )
    return PaginatedResponse.create(items, total, page, page_size)


# ── Job Applications ──────────────────────────────────────────


@router.get(
    "/applications",
    response_model=PaginatedResponse[JobApplicationListResponse],
    dependencies=[RequireAdmin],
)
async def list_applications(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    position_id: UUID | None = None,
    status: str | None = None,
):
    """List all job applications (admin)."""
    service = CareerService(db)
    items, total = await service.list_applications(
        page=page,
        page_size=page_size,
        position_id=position_id,
        status=status,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/applications/{application_id}",
    response_model=JobApplicationResponse,
    dependencies=[RequireAdmin],
)
async def get_application(application_id: UUID, db: DatabaseSession):
    """Get a single application detail (admin)."""
    service = CareerService(db)
    application = await service.get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.put(
    "/applications/{application_id}/status",
    response_model=JobApplicationResponse,
    dependencies=[RequireAdmin],
)
async def update_application_status(
    application_id: UUID,
    data: JobApplicationStatusUpdate,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    """Update application status (reviewing, shortlisted, hired, rejected, etc.)."""
    service = CareerService(db)
    try:
        return await service.update_application_status(
            application_id, data, reviewed_by=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
