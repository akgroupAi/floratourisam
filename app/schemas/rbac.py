"""RBAC (Role-Based Access Control) schemas."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


# ============== Permission Schemas ==============

class PermissionCreate(BaseModel):
    """Schema for creating a new permission."""
    name: str = Field(..., description="Permission name (e.g., 'users.create')")
    resource: str = Field(..., description="Resource name (e.g., 'users', 'doctors')")
    action: str = Field(..., description="Action type (e.g., 'create', 'read', 'update', 'delete', 'manage')")
    description: Optional[str] = Field(None, description="Permission description")


class PermissionUpdate(BaseModel):
    """Schema for updating a permission."""
    name: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    description: Optional[str] = None


class PermissionResponse(BaseSchema):
    """Schema for permission response."""
    id: UUID
    name: str
    resource: str
    action: str
    description: Optional[str] = None


# ============== Role Schemas ==============

class RoleCreate(BaseModel):
    """Schema for creating a new role."""
    name: str = Field(..., description="Role name (e.g., 'ADMIN', 'DOCTOR')")
    description: Optional[str] = Field(None, description="Role description")
    permission_ids: List[UUID] = Field(default_factory=list, description="List of permission IDs to assign")


class RoleUpdate(BaseModel):
    """Schema for updating a role."""
    name: Optional[str] = None
    description: Optional[str] = None


class RoleResponse(BaseSchema):
    """Schema for role response."""
    id: UUID
    name: str
    description: Optional[str] = None
    is_system_role: bool
    permissions: List[PermissionResponse] = []


class RoleListResponse(BaseSchema):
    """Schema for role list response (without permissions)."""
    id: UUID
    name: str
    description: Optional[str] = None
    is_system_role: bool
    permission_count: int = 0


# ============== Assignment Schemas ==============

class AssignPermissionsToRole(BaseModel):
    """Schema for assigning permissions to a role."""
    permission_ids: List[UUID] = Field(..., description="List of permission IDs to assign")


class AssignRolesToUser(BaseModel):
    """Schema for assigning roles to a user."""
    role_ids: List[UUID] = Field(..., description="List of role IDs to assign")


class UserRolesResponse(BaseSchema):
    """Schema for user roles response."""
    user_id: UUID
    roles: List[RoleListResponse]
    permissions: List[str]  # Flattened list of all permission names
