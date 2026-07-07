"""Admin contact submission management."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.contact import (
    ContactDetailResponse,
    ContactListItem,
    ContactStatsResponse,
    ContactStatusUpdate,
)
from app.services.contact_service import ContactService
from app.utils.enums import ContactStatus

router = APIRouter()


@router.get(
    "/stats",
    response_model=ContactStatsResponse,
    dependencies=[RequireAdmin],
    summary="Contact submission statistics",
)
async def get_contact_stats(db: DatabaseSession):
    """Return counts by status so admins can spot new inquiries quickly."""
    service = ContactService(db)
    return await service.get_stats()


@router.get(
    "",
    response_model=PaginatedResponse[ContactListItem],
    dependencies=[RequireAdmin],
    summary="List contact submissions",
)
async def list_contacts(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[ContactStatus] = Query(None, description="Filter by status"),
    country: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search name, email, or phone"),
    new_only: bool = Query(False, description="Only show new/pending submissions"),
):
    """List all contact form submissions for the admin panel."""
    service = ContactService(db)
    items, total = await service.list_contacts(
        page=page,
        page_size=page_size,
        status=status.value if status else None,
        country=country,
        search=search,
        new_only=new_only,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/{contact_id}",
    response_model=ContactDetailResponse,
    dependencies=[RequireAdmin],
    summary="Get contact submission detail",
)
async def get_contact_detail(
    contact_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    View a contact submission.

    When opened for the first time, a pending submission is automatically
    marked as **in_process**.
    """
    service = ContactService(db)
    contact = await service.get_contact(contact_id, viewed_by=current_user.id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return contact


@router.patch(
    "/{contact_id}/status",
    response_model=ContactDetailResponse,
    dependencies=[RequireAdmin],
    summary="Update contact submission status",
)
async def update_contact_status(
    contact_id: UUID,
    data: ContactStatusUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update contact status (e.g. mark as completed after follow-up)."""
    service = ContactService(db)
    try:
        return await service.update_status(contact_id, data, updated_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/{contact_id}",
    response_model=MessageResponse,
    dependencies=[RequireAdmin],
    summary="Delete contact submission",
)
async def delete_contact(
    contact_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Soft-delete a contact submission."""
    from sqlalchemy import select

    from app.models.site import LeadSubmission

    result = await db.execute(
        select(LeadSubmission).where(
            LeadSubmission.id == contact_id,
            LeadSubmission.form_source == "contact_page",
            LeadSubmission.is_deleted == False,
        )
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    lead.soft_delete(current_user.id)
    await db.commit()
    return MessageResponse(message="Contact submission deleted successfully")
