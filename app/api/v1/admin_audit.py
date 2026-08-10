"""Unified audit trail — who changed what, across every audited entity."""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DatabaseSession, RequireAdmin
from app.schemas.audit import AuditActorSummary, AuditEvent
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services.audit_service import AuditService

router = APIRouter()


@router.get(
    "/entity-types",
    response_model=List[str],
    dependencies=[RequireAdmin],
    summary="Entity types covered by the audit feed",
)
async def list_entity_types():
    """The values accepted by the `entity_type` filter."""
    return AuditService.entity_types()


@router.get(
    "",
    response_model=PaginatedResponse[AuditEvent],
    dependencies=[RequireAdmin],
    summary="Audit feed",
)
async def get_audit_feed(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    entity_type: Optional[str] = Query(None, description="See /entity-types"),
    entity_id: Optional[UUID] = Query(None),
    actor_id: Optional[UUID] = Query(None, description="Everything one user changed"),
    action: Optional[str] = Query(None, description="created | updated | deleted"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    """
    Chronological feed of create, update, and delete events across the platform.

    Built from the `created_by` / `updated_by` / `deleted_by` columns every table
    already carries. Note the limits: `updated_by` holds only the **most recent**
    editor, so repeated edits collapse into one event, and no before/after field values
    are available.
    """
    items, total = await AuditService(db).get_feed(
        PaginationParams(page=page, page_size=page_size),
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        from_date=from_date,
        to_date=to_date,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/entity/{entity_type}/{entity_id}",
    response_model=PaginatedResponse[AuditEvent],
    dependencies=[RequireAdmin],
    summary="History for one record",
)
async def get_entity_history(
    entity_type: str,
    entity_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """Everything recorded against a single record — who created it, last changed it, deleted it."""
    try:
        items, total = await AuditService(db).get_entity_history(
            entity_type, entity_id, PaginationParams(page=page, page_size=page_size)
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/user/{actor_id}/summary",
    response_model=AuditActorSummary,
    dependencies=[RequireAdmin],
    summary="What one user changed",
)
async def get_actor_summary(
    actor_id: UUID,
    db: DatabaseSession,
    days: int = Query(30, ge=1, le=365),
):
    """
    Activity summary for one user, counted by entity type and action.

    Useful for reviewing what an external hotel, apartment, or restaurant manager has
    been touching.
    """
    return await AuditService(db).get_actor_summary(actor_id, days=days)
