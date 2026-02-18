"""User model for authentication and authorization."""

import uuid
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime


from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.utils.enums import UserRole

from app.models.patient import Patient
from app.models.doctor import Doctor


class User(BaseModel):
    """User model for authentication and profile management."""

    __tablename__ = "users"

    # Authentication fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Profile fields
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Role and permissions
    role: Mapped[str] = mapped_column(
        String(50),
        default=UserRole.PATIENT.value,
        nullable=False,
        index=True,
    )

    # Status flags
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Verification
    verification_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    verification_token_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Password reset
    reset_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    reset_token_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Session tracking
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_login_ip: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )

    # Refresh token (for JWT)
    refresh_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    patient_profile: Mapped[Optional[Patient]] = relationship(
        Patient,
        back_populates="user",
        foreign_keys=[Patient.user_id],
        uselist=False,
        lazy="selectin",
    )
    doctor_profile: Mapped[Optional[Doctor]] = relationship(
        Doctor,
        back_populates="user",
        foreign_keys=[Doctor.user_id],
        uselist=False,
        lazy="selectin",
    )
    
    # RBAC relationships
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        Index("ix_users_email_active", "email", "is_active"),
        Index("ix_users_role_active", "role", "is_active"),
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email}, role={self.role})"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.role in [UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value]

    @property
    def is_superuser(self) -> bool:
        """Check if user is superuser."""
        return self.role == UserRole.SUPER_ADMIN.value
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        return any(r.name == role_name for r in self.roles)
    
    def has_permission(self, permission_name: str) -> bool:
        """Check if user has a specific permission through any of their roles."""
        for role in self.roles:
            if role.has_permission(permission_name):
                return True
        return False
    
    def get_all_permissions(self) -> List[str]:
        """Get all permissions from all roles."""
        permissions = set()
        for role in self.roles:
            permissions.update(role.get_permission_names())
        return list(permissions)
