"""RBAC (Role-Based Access Control) models."""

import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Column, ForeignKey, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


# Association table for Role-Permission many-to-many relationship
role_permissions = Table(
    "role_permissions",
    BaseModel.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


# Association table for User-Role many-to-many relationship
user_roles = Table(
    "user_roles",
    BaseModel.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(BaseModel):
    """Permission model for granular access control."""

    __tablename__ = "permissions"

    # Permission identifier
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )  # e.g., "users.create", "doctors.view"

    # Resource and action breakdown
    resource: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # e.g., "users", "doctors", "bookings"

    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # e.g., "create", "read", "update", "delete", "manage"

    # Description
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions",
    )

    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
    )

    def __repr__(self) -> str:
        return f"Permission(name={self.name}, resource={self.resource}, action={self.action})"


class Role(BaseModel):
    """Role model for grouping permissions."""

    __tablename__ = "roles"

    # Role identifier
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )  # e.g., "SUPER_ADMIN", "ADMIN", "DOCTOR", "PATIENT"

    # Description
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )

    # System role flag (cannot be deleted)
    is_system_role: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )

    users: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
    )

    def __repr__(self) -> str:
        return f"Role(name={self.name}, permissions={len(self.permissions)})"

    def has_permission(self, permission_name: str) -> bool:
        """Check if role has a specific permission."""
        return any(p.name == permission_name for p in self.permissions)

    def get_permission_names(self) -> List[str]:
        """Get list of all permission names for this role."""
        return [p.name for p in self.permissions]
