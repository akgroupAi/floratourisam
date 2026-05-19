"""RBAC API Schemas."""

from datetime import datetime
from typing import Optional, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


# ============== ROLE SCHEMAS ==============

class RoleCreate(BaseModel):
    """Create role request."""
    name: str = Field(..., min_length=2, max_length=50, description="Role name (e.g., 'hotel_manager')")
    label: str = Field(..., min_length=2, max_length=100, description="Display label (e.g., 'Hotel Manager')")
    description: Optional[str] = Field(None, max_length=500)
    is_active: bool = Field(True, description="Whether the role is active immediately upon creation")


class RoleUpdate(BaseModel):
    """Update role request."""
    label: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class RolePermissionsUpdate(BaseModel):
    """Update role permissions matrix."""
    permissions: Dict[str, Dict[str, bool]] = Field(
        ...,
        description="Matrix: {resource: {can_create, can_read, can_update, can_delete}}"
    )
    scope_own_only: bool = Field(False, description="Restrict to own resources only")


class RoleResponse(BaseSchema):
    """Role response with metadata."""
    id: UUID
    name: str
    label: str
    description: Optional[str]
    is_system_role: bool
    is_active: bool
    users_count: int
    scope_own_only: bool
    created_at: datetime
    updated_at: datetime


class RoleDetailResponse(RoleResponse):
    """Role with full permissions matrix."""
    permissions: Dict[str, Dict[str, bool]]


# ============== PERMISSION SCHEMAS ==============

class PermissionResponse(BaseModel):
    """Permission response."""
    id: UUID
    name: str
    resource: str
    action: str
    description: Optional[str]


class RolePermissionsResponse(BaseModel):
    """Permissions for a role."""
    role_id: UUID
    role_name: str
    scope_own_only: bool
    permissions: Dict[str, Dict[str, bool]]


# ============== USER ROLE ASSIGNMENT SCHEMAS ==============

class UserRoleAssign(BaseModel):
    """Assign role to user."""
    user_id: Optional[UUID] = None
    email: Optional[str] = None
    role_id: UUID

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@hotel.com",
                "role_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class UserRoleResponse(BaseModel):
    """User-role assignment."""
    id: UUID
    user_id: UUID
    user_email: str
    user_name: str
    role_id: UUID
    role_name: str
    role_label: str
    assigned_at: datetime


class UserWithRoleResponse(BaseModel):
    """User with their role and assigned resources."""
    user_id: UUID
    email: str
    full_name: str
    role: str
    role_label: str
    assigned_resources: Dict[str, List[Dict]]  # {hotels: [...], apartments: [...], restaurants: [...]}
    assigned_at: datetime


# ============== ENTITY MANAGER ASSIGNMENT SCHEMAS ==============

class EntityManagerAssign(BaseModel):
    """Assign manager to entity."""
    manager_user_id: Optional[UUID] = Field(None, description="Manager user ID, or null to unassign")
    manager_email: Optional[str] = Field(None, description="Manager email (alternative to user_id)")


class EntityWithManagerResponse(BaseModel):
    """Entity with manager info."""
    id: UUID
    name: str
    city: str
    country: str
    manager_id: Optional[UUID]
    manager_email: Optional[str]
    manager_name: Optional[str]
    is_active: bool


class ManagerListResponse(BaseModel):
    """Available manager for assignment."""
    user_id: UUID
    email: str
    full_name: str
    role: str
    assigned_count: int


# ============== STATS SCHEMAS ==============

class RBACStatsResponse(BaseModel):
    """RBAC dashboard statistics."""
    total_roles: int
    assigned_users: int
    admin_users: int
    hotels_with_manager: int
    apartments_with_manager: int
    restaurants_with_manager: int


# ============== AUDIT LOG SCHEMAS ==============

class AuditLogResponse(BaseModel):
    """Audit log entry."""
    id: UUID
    actor_user_id: Optional[UUID]
    actor_email: Optional[str]
    action: str
    target_type: str
    target_id: Optional[UUID]
    target_name: Optional[str]
    description: Optional[str]
    meta_data: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Paginated audit logs."""
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
