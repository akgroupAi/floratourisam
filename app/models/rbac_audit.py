"""RBAC Audit Log Model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SimpleBaseModel


class RBACauditLog(SimpleBaseModel):
    """RBAC audit log for tracking role/permission changes."""

    __tablename__ = "rbac_audit_logs"

    # Actor information
    actor_user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User who performed the action"
    )
    actor_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Email of the actor (for deleted users)"
    )

    # Action information
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Action performed: assign_role, remove_role, update_permissions, assign_manager, etc."
    )

    # Target information
    target_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="What was changed: role, user, hotel, apartment, restaurant"
    )

    target_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of the target (user_id, role_id, hotel_id, etc.)"
    )

    target_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Human-readable name of target (user email, role name, hotel name)"
    )

    # Details
    meta_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional details: old_value, new_value, affected_entities, etc."
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description of the action"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"RBACauditLog(action={self.action}, target_type={self.target_type}, actor={self.actor_email})"
