"""User schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import BaseSchema
from app.utils.enums import UserRole


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)


class UserCreate(UserBase):
    """User creation schema."""

    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.PATIENT


class UserUpdate(BaseModel):
    """User update schema."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    avatar_url: Optional[str] = Field(default=None, max_length=500)


class UserAdminUpdate(UserUpdate):
    """Admin user update schema."""

    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserResponse(BaseSchema):
    """User response schema."""

    id: UUID
    email: str
    full_name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class UserListResponse(BaseSchema):
    """User list response schema."""

    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime


class UserProfileResponse(UserResponse):
    """User profile response with additional details."""

    has_patient_profile: bool = False
    has_doctor_profile: bool = False


class CurrentUserResponse(BaseSchema):
    """Current user response."""

    id: UUID
    email: str
    full_name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    permissions: list[str] = []


class UserStatsResponse(BaseModel):
    """User statistics response."""

    total_users: int
    active_users: int
    verified_users: int
    users_by_role: dict[str, int]
    new_users_today: int
    new_users_this_week: int
    new_users_this_month: int
