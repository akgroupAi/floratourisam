"""Event/calendar endpoints."""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DatabaseSession
from app.models.system import Event
from app.schemas.common import PaginatedResponse
from app.schemas.system import EventCreate, EventUpdate, EventResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[EventResponse])
async def list_events(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    """List user's events."""
    query = select(Event).where(Event.user_id == current_user.id, Event.is_deleted == False)
    
    if status:
        query = query.where(Event.status == status)
    if event_type:
        query = query.where(Event.event_type == event_type)
    if start_date:
        query = query.where(Event.start_time >= start_date)
    if end_date:
        query = query.where(Event.start_time <= end_date)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(Event.start_time.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    return PaginatedResponse.create(events, total, page, page_size)


@router.get("/calendar")
async def get_calendar_view(
    current_user: CurrentUser,
    db: DatabaseSession,
    start_date: datetime,
    end_date: datetime,
    event_types: Optional[str] = None,  # comma-separated
):
    """Get events for calendar view."""
    query = select(Event).where(
        Event.user_id == current_user.id,
        Event.is_deleted == False,
        Event.start_time >= start_date,
        Event.start_time <= end_date,
    )
    
    if event_types:
        types = event_types.split(",")
        query = query.where(Event.event_type.in_(types))
    
    result = await db.execute(query.order_by(Event.start_time))
    events = result.scalars().all()
    
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "events": [EventResponse.model_validate(e) for e in events],
    }


@router.get("/upcoming")
async def get_upcoming_events(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(5, ge=1, le=20),
):
    """Get upcoming events."""
    now = datetime.now(timezone.utc)
    
    result = await db.execute(
        select(Event)
        .where(
            Event.user_id == current_user.id,
            Event.is_deleted == False,
            Event.start_time >= now,
            Event.status.in_(["scheduled", "confirmed"]),
        )
        .order_by(Event.start_time.asc())
        .limit(limit)
    )
    events = result.scalars().all()
    
    return {"events": [EventResponse.model_validate(e) for e in events]}


@router.post("", response_model=EventResponse)
async def create_event(data: EventCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create an event."""
    event = Event(
        user_id=current_user.id,
        **data.model_dump(),
        created_by=current_user.id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Get event by ID."""
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(event_id: UUID, data: EventUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update an event."""
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    event.updated_by = current_user.id
    await db.commit()
    return event


@router.delete("/{event_id}")
async def delete_event(event_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete an event."""
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Event deleted"}


@router.post("/{event_id}/cancel")
async def cancel_event(event_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Cancel an event."""
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event.status = "cancelled"
    event.updated_by = current_user.id
    await db.commit()
    return {"message": "Event cancelled"}


@router.post("/{event_id}/complete")
async def complete_event(event_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Mark event as completed."""
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event.status = "completed"
    event.updated_by = current_user.id
    await db.commit()
    return {"message": "Event completed"}


@router.post("/{event_id}/reschedule")
async def reschedule_event(
    event_id: UUID,
    new_start_time: datetime,
    new_end_time: Optional[datetime] = None,
    current_user: CurrentUser = None,
    db: DatabaseSession = None,
):
    """Reschedule an event."""
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Calculate duration and apply to new time
    if event.end_time and not new_end_time:
        duration = event.end_time - event.start_time
        new_end_time = new_start_time + duration
    
    event.start_time = new_start_time
    event.end_time = new_end_time
    event.updated_by = current_user.id
    await db.commit()
    
    return {"message": "Event rescheduled", "new_start_time": new_start_time.isoformat()}
