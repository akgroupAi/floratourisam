"""Notification endpoints."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DatabaseSession
from app.models.system import Notification
from app.schemas.common import PaginatedResponse
from app.schemas.system import (
    NotificationResponse, NotificationListResponse, NotificationMarkRead,
    NotificationPreferences,
)

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_read: Optional[bool] = None,
):
    """List user's notifications."""
    query = select(Notification).where(
        Notification.user_id == current_user.id,
        Notification.is_deleted == False
    )
    
    if is_read is not None:
        query = query.where(Notification.is_read == is_read)
    
    # Count total
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Count unread
    unread_result = await db.execute(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    unread_count = unread_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Notification.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count")
async def get_unread_count(current_user: CurrentUser, db: DatabaseSession):
    """Get unread notification count."""
    result = await db.execute(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    return {"unread_count": result.scalar() or 0}


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(notification_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Get notification by ID."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Mark single notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {"message": "Notification marked as read"}


@router.post("/mark-read")
async def mark_multiple_read(data: NotificationMarkRead, current_user: CurrentUser, db: DatabaseSession):
    """Mark multiple notifications as read."""
    await db.execute(
        update(Notification)
        .where(
            Notification.id.in_(data.notification_ids),
            Notification.user_id == current_user.id
        )
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    
    return {"message": f"{len(data.notification_ids)} notifications marked as read"}


@router.post("/mark-all-read")
async def mark_all_read(current_user: CurrentUser, db: DatabaseSession):
    """Mark all notifications as read."""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    
    return {"message": "All notifications marked as read"}


@router.delete("/{notification_id}")
async def delete_notification(notification_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete a notification."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.soft_delete(current_user.id)
    await db.commit()
    
    return {"message": "Notification deleted"}


@router.get("/preferences", response_model=NotificationPreferences)
async def get_preferences(current_user: CurrentUser, db: DatabaseSession):
    """Get notification preferences."""
    # Would fetch from user preferences table
    return NotificationPreferences()


@router.put("/preferences", response_model=NotificationPreferences)
async def update_preferences(data: NotificationPreferences, current_user: CurrentUser, db: DatabaseSession):
    """Update notification preferences."""
    # Would update user preferences table
    return data
