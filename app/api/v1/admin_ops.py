"""Admin operations — notification broadcasts, platform calendar, demand signals."""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.admin_ops import (
    AdminEventResponse,
    AdminNotificationResponse,
    BroadcastRequest,
    BroadcastResponse,
    FavoriteStatsResponse,
    NotificationStatsResponse,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.treatment_proposal import AdminProposalStatsResponse
from app.services.admin_ops_service import AdminOpsService

notification_router = APIRouter()
event_router = APIRouter()
insight_router = APIRouter()


# ── Notifications ─────────────────────────────────────────────


@notification_router.post(
    "/broadcast",
    response_model=BroadcastResponse,
    dependencies=[RequireAdmin],
    summary="Broadcast a notification",
)
async def broadcast_notification(
    data: BroadcastRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    Send a notification to every user holding the given roles, or to an explicit list.

    Notifications are created in the database and pushed over WebSocket to anyone
    connected. Only active, non-deleted users are targeted.

    You must name an audience — `roles` or `user_ids`. A request with neither is
    rejected rather than quietly messaging the whole platform.
    """
    try:
        return await AdminOpsService(db).broadcast(
            title=data.title,
            message=data.message,
            sent_by=current_user.id,
            roles=data.roles,
            user_ids=data.user_ids,
            notification_type=data.notification_type,
            action_url=data.action_url,
            action_text=data.action_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@notification_router.get(
    "/stats",
    response_model=NotificationStatsResponse,
    dependencies=[RequireAdmin],
    summary="Notification statistics",
)
async def get_notification_stats(db: DatabaseSession):
    """Volume, read-through rate, and breakdown by type."""
    return await AdminOpsService(db).notification_stats()


@notification_router.get(
    "",
    response_model=PaginatedResponse[AdminNotificationResponse],
    dependencies=[RequireAdmin],
    summary="List all notifications",
)
async def list_notifications(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[UUID] = Query(None),
    notification_type: Optional[str] = Query(None),
    is_read: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Title or message text"),
):
    """Notifications across every user, newest first."""
    items, total = await AdminOpsService(db).list_notifications(
        PaginationParams(page=page, page_size=page_size),
        user_id=user_id,
        notification_type=notification_type,
        is_read=is_read,
        search=search,
    )
    return PaginatedResponse.create(items, total, page, page_size)


# ── Platform calendar ─────────────────────────────────────────


@event_router.get(
    "",
    response_model=PaginatedResponse[AdminEventResponse],
    dependencies=[RequireAdmin],
    summary="Platform-wide calendar",
)
async def list_events(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[UUID] = Query(None),
    event_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    upcoming_only: bool = Query(False, description="Only future events, soonest first"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    """Every user's calendar events in one place."""
    items, total = await AdminOpsService(db).list_events(
        PaginationParams(page=page, page_size=page_size),
        user_id=user_id,
        event_type=event_type,
        status=status,
        upcoming_only=upcoming_only,
        from_date=from_date,
        to_date=to_date,
    )
    return PaginatedResponse.create(items, total, page, page_size)


# ── Demand signals ────────────────────────────────────────────


@insight_router.get(
    "/favorites",
    response_model=FavoriteStatsResponse,
    dependencies=[RequireAdmin],
    summary="What patients are saving",
)
async def get_favorite_stats(
    db: DatabaseSession,
    limit: int = Query(10, ge=1, le=50, description="Top N per entity type"),
):
    """
    Saved-item counts by entity type, with the most-saved doctors, hospitals, hotels,
    apartments, restaurants, and packages.

    A demand signal: what patients bookmark but may not have booked yet.
    """
    return await AdminOpsService(db).favorite_stats(limit=limit)


@insight_router.get(
    "/treatment-proposals",
    response_model=AdminProposalStatsResponse,
    dependencies=[RequireAdmin],
    summary="Treatment proposal funnel",
)
async def get_proposal_stats(db: DatabaseSession):
    """
    Proposal counts by status and pipeline value — total proposed against total accepted.

    Identical to `GET /admin/treatment-proposals/stats`; both call the same code.
    """
    return await AdminOpsService(db).proposal_stats()
