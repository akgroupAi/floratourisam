"""Admin operations schemas — broadcasts, calendar, demand signals."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class BroadcastRequest(BaseModel):
    """Send a notification to a set of users.

    Supply either `roles` or `user_ids`. Supplying neither is rejected rather than
    silently messaging every user on the platform.
    """

    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=2000)
    roles: Optional[List[str]] = Field(
        None, description="e.g. ['patient'] or ['doctor', 'hotel_manager']"
    )
    user_ids: Optional[List[UUID]] = Field(None, description="Explicit recipients")
    notification_type: str = Field("system", max_length=50)
    action_url: Optional[str] = Field(None, max_length=500)
    action_text: Optional[str] = Field(None, max_length=100)

    @model_validator(mode="after")
    def require_an_audience(self):
        if not self.roles and not self.user_ids:
            raise ValueError("Specify roles or user_ids — refusing to broadcast to everyone implicitly")
        return self


class BroadcastResponse(BaseModel):
    """Result of a broadcast."""

    recipients_targeted: int
    notifications_created: int


class AdminNotificationResponse(BaseModel):
    """Notification row for admin."""

    id: UUID
    user_id: Optional[UUID] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    title: str
    message: Optional[str] = None
    notification_type: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    action_url: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    sent_push: bool = False
    sent_email: bool = False
    created_at: datetime


class NotificationStatsResponse(BaseModel):
    """Notification volume and read-through."""

    total: int
    read: int
    unread: int
    read_rate: float
    sent_last_24h: int
    by_type: Dict[str, int]


class AdminEventResponse(BaseModel):
    """Calendar event row for admin."""

    id: UUID
    user_id: Optional[UUID] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    title: str
    description: Optional[str] = None
    event_type: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    all_day: bool = False
    location: Optional[str] = None
    location_type: Optional[str] = None
    meeting_url: Optional[str] = None
    status: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    created_at: datetime


class FavoriteEntry(BaseModel):
    """One frequently saved item."""

    entity_id: str
    name: Optional[str] = None
    saved_count: int


class FavoriteStatsResponse(BaseModel):
    """What patients are saving — demand signal for catalogue decisions."""

    total_favorites: int
    patients_with_favorites: int
    by_entity_type: Dict[str, int]
    most_saved: Dict[str, List[FavoriteEntry]]


class ProposalStatsResponse(BaseModel):
    """Treatment proposal funnel and pipeline value."""

    total: int
    by_status: Dict[str, int]
    pending_admin_review: int
    admin_approved: int
    accepted: int
    acceptance_rate: float
    total_proposed_value: float
    accepted_value: float
    average_proposal_value: float
