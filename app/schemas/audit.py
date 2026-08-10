"""Audit trail schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """One create, update, or delete recorded against a record."""

    entity_type: str
    entity_id: str
    entity_label: Optional[str] = Field(
        None, description="Human-readable name or reference for the record, when it has one"
    )
    action: str = Field(..., description="created | updated | deleted")
    actor_id: Optional[UUID] = None
    actor_name: Optional[str] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    occurred_at: datetime


class AuditActorSummary(BaseModel):
    """What one user changed over a window."""

    actor_id: str
    days: int
    total_actions: int = 0
    by_entity_type: dict[str, dict[str, int]] = {}
    by_action: dict[str, int] = {}
