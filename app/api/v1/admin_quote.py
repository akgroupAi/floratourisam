"""Admin quote request management ('Get a Free Medical Plan Quote' form)."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.quote import (
    QuoteAssignUpdate,
    QuoteDetailResponse,
    QuoteListItem,
    QuoteStatsResponse,
    QuoteStatusUpdate,
)
from app.services.quote_service import QuoteService
from app.utils.enums import QuoteStatus

router = APIRouter()


@router.get(
    "/stats",
    response_model=QuoteStatsResponse,
    dependencies=[RequireAdmin],
    summary="Quote request statistics",
)
async def get_quote_stats(db: DatabaseSession):
    """Return counts by funnel stage plus the conversion rate."""
    service = QuoteService(db)
    return await service.get_stats()


@router.get(
    "",
    response_model=PaginatedResponse[QuoteListItem],
    dependencies=[RequireAdmin],
    summary="List quote requests",
)
async def list_quotes(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[QuoteStatus] = Query(None, description="Filter by funnel stage"),
    country: Optional[str] = Query(None),
    medical_condition: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search name, email, or phone"),
    new_only: bool = Query(False, description="Only show new/unworked requests"),
    has_documents: Optional[bool] = Query(None, description="Filter by document attachments"),
    sort_by: str = Query("created_at", pattern="^(created_at|name|email|country)$"),
):
    """List all medical plan quote requests for the admin panel."""
    service = QuoteService(db)
    items, total = await service.list_quotes(
        page=page,
        page_size=page_size,
        status=status.value if status else None,
        country=country,
        medical_condition=medical_condition,
        search=search,
        new_only=new_only,
        has_documents=has_documents,
        sort_by=sort_by,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/{quote_id}",
    response_model=QuoteDetailResponse,
    dependencies=[RequireAdmin],
    summary="Get quote request detail",
)
async def get_quote_detail(quote_id: UUID, db: DatabaseSession):
    """
    View a quote request, including uploaded medical documents.

    Unlike contact submissions, opening a quote does **not** change its status —
    funnel stages represent real outreach, so an admin sets them explicitly.
    """
    service = QuoteService(db)
    quote = await service.get_quote(quote_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
    return quote


@router.patch(
    "/{quote_id}/status",
    response_model=QuoteDetailResponse,
    dependencies=[RequireAdmin],
    summary="Update quote request status",
)
async def update_quote_status(
    quote_id: UUID,
    data: QuoteStatusUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Move a quote through the funnel: new → contacted → qualified → converted."""
    service = QuoteService(db)
    try:
        return await service.update_status(quote_id, data, updated_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch(
    "/{quote_id}/assign",
    response_model=QuoteDetailResponse,
    dependencies=[RequireAdmin],
    summary="Assign quote request to a team member",
)
async def assign_quote(
    quote_id: UUID,
    data: QuoteAssignUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Assign a quote request to the team member who will follow up."""
    service = QuoteService(db)
    try:
        return await service.assign(quote_id, data.assigned_to, updated_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/{quote_id}",
    response_model=MessageResponse,
    dependencies=[RequireAdmin],
    summary="Delete quote request",
)
async def delete_quote(
    quote_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Soft-delete a quote request."""
    service = QuoteService(db)
    if not await service.delete(quote_id, deleted_by=current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
    return MessageResponse(message="Quote request deleted successfully")
