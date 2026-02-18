"""RBAC (Role-Based Access Control) API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func, or_, delete as sql_delete
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.rbac import Permission, Role, role_permissions, user_roles
from app.models.user import User
from app.schemas.rbac import (
    PermissionCreate, PermissionUpdate, PermissionResponse,
    RoleCreate, RoleUpdate, RoleResponse, RoleListResponse,
    AssignPermissionsToRole, AssignRolesToUser, UserRolesResponse,
)
from app.schemas.common import PaginatedResponse, MessageResponse

router = APIRouter()


# ============== PERMISSION ENDPOINTS ==============

@router.get("/permissions", dependencies=[RequireAdmin])
async def list_permissions(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    resource: Optional[str] = None,
    action: Optional[str] = None,
    search: Optional[str] = None,
):
    """List all permissions with optional filtering."""
    query = select(Permission).where(Permission.is_deleted == False)
    
    if resource:
        query = query.where(Permission.resource == resource)
    if action:
        query = query.where(Permission.action == action)
    if search:
        query = query.where(
            or_(
                Permission.name.ilike(f"%{search}%"),
                Permission.description.ilike(f"%{search}%")
            )
        )
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Permission.resource, Permission.action)
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    permissions = result.scalars().all()
    
    return PaginatedResponse.create(permissions, total, page, page_size)


@router.post("/permissions", response_model=PermissionResponse, dependencies=[RequireAdmin])
async def create_permission(data: PermissionCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new permission."""
    # Check if permission already exists
    existing = await db.execute(
        select(Permission).where(Permission.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Permission '{data.name}' already exists"
        )
    
    permission = Permission(
        name=data.name,
        resource=data.resource,
        action=data.action,
        description=data.description,
        created_by=current_user.id,
    )
    
    db.add(permission)
    await db.commit()
    await db.refresh(permission)
    
    return permission


@router.get("/permissions/{permission_id}", response_model=PermissionResponse, dependencies=[RequireAdmin])
async def get_permission(permission_id: UUID, db: DatabaseSession):
    """Get permission details."""
    result = await db.execute(
        select(Permission).where(Permission.id == permission_id, Permission.is_deleted == False)
    )
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    return permission


@router.put("/permissions/{permission_id}", response_model=PermissionResponse, dependencies=[RequireAdmin])
async def update_permission(
    permission_id: UUID,
    data: PermissionUpdate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Update permission."""
    result = await db.execute(
        select(Permission).where(Permission.id == permission_id, Permission.is_deleted == False)
    )
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    # Update fields
    if data.name is not None:
        permission.name = data.name
    if data.resource is not None:
        permission.resource = data.resource
    if data.action is not None:
        permission.action = data.action
    if data.description is not None:
        permission.description = data.description
    
    permission.updated_by = current_user.id
    await db.commit()
    await db.refresh(permission)
    
    return permission


@router.delete("/permissions/{permission_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_permission(permission_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft delete permission."""
    result = await db.execute(
        select(Permission).where(Permission.id == permission_id, Permission.is_deleted == False)
    )
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    permission.is_deleted = True
    permission.deleted_by = current_user.id
    await db.commit()
    
    return MessageResponse(message="Permission deleted successfully")


# ============== ROLE ENDPOINTS ==============

@router.get("/roles", dependencies=[RequireAdmin])
async def list_roles(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
):
    """List all roles."""
    query = select(Role).where(Role.is_deleted == False)
    
    if search:
        query = query.where(
            or_(
                Role.name.ilike(f"%{search}%"),
                Role.description.ilike(f"%{search}%")
            )
        )
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Role.name)
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    roles = result.scalars().all()
    
    # Convert to list response (without full permissions)
    items = [
        RoleListResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system_role=role.is_system_role,
            permission_count=len(role.permissions),
            created_at=role.created_at,
            updated_at=role.updated_at,
        )
        for role in roles
    ]
    
    return PaginatedResponse.create(items, total, page, page_size)


@router.post("/roles", response_model=RoleResponse, dependencies=[RequireAdmin])
async def create_role(data: RoleCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new role."""
    # Check if role already exists
    existing = await db.execute(
        select(Role).where(Role.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{data.name}' already exists"
        )
    
    role = Role(
        name=data.name,
        description=data.description,
        is_system_role=False,
        created_by=current_user.id,
    )
    
    # Assign permissions if provided
    if data.permission_ids:
        permissions_result = await db.execute(
            select(Permission).where(Permission.id.in_(data.permission_ids))
        )
        permissions = permissions_result.scalars().all()
        role.permissions = permissions
    
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    return role


@router.get("/roles/{role_id}", response_model=RoleResponse, dependencies=[RequireAdmin])
async def get_role(role_id: UUID, db: DatabaseSession):
    """Get role details with permissions."""
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id, Role.is_deleted == False)
    )
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    return role


@router.put("/roles/{role_id}", response_model=RoleResponse, dependencies=[RequireAdmin])
async def update_role(role_id: UUID, data: RoleUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update role."""
    result = await db.execute(
        select(Role).where(Role.id == role_id, Role.is_deleted == False)
    )
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Prevent updating system roles
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system roles"
        )
    
    # Update fields
    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    
    role.updated_by = current_user.id
    await db.commit()
    await db.refresh(role)
    
    return role


@router.delete("/roles/{role_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def delete_role(role_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft delete role."""
    result = await db.execute(
        select(Role).where(Role.id == role_id, Role.is_deleted == False)
    )
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Prevent deleting system roles
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system roles"
        )
    
    role.is_deleted = True
    role.deleted_by = current_user.id
    await db.commit()
    
    return MessageResponse(message="Role deleted successfully")


# ============== ROLE-PERMISSION ASSIGNMENT ==============

@router.post("/roles/{role_id}/permissions", response_model=RoleResponse, dependencies=[RequireAdmin])
async def assign_permissions_to_role(
    role_id: UUID,
    data: AssignPermissionsToRole,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Assign permissions to a role (replaces existing permissions)."""
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id, Role.is_deleted == False)
    )
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Get permissions
    permissions_result = await db.execute(
        select(Permission).where(Permission.id.in_(data.permission_ids))
    )
    permissions = permissions_result.scalars().all()
    
    # Replace permissions
    role.permissions = permissions
    role.updated_by = current_user.id
    
    await db.commit()
    await db.refresh(role)
    
    return role


@router.delete("/roles/{role_id}/permissions/{permission_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def remove_permission_from_role(
    role_id: UUID,
    permission_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Remove a permission from a role."""
    # Delete from association table
    await db.execute(
        sql_delete(role_permissions).where(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == permission_id
        )
    )
    await db.commit()
    
    return MessageResponse(message="Permission removed from role")


# ============== USER-ROLE ASSIGNMENT ==============

@router.get("/users/{user_id}/roles", response_model=UserRolesResponse, dependencies=[RequireAdmin])
async def get_user_roles(user_id: UUID, db: DatabaseSession):
    """Get user's roles and permissions."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == user_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build response
    roles_list = [
        RoleListResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system_role=role.is_system_role,
            permission_count=len(role.permissions),
            created_at=role.created_at,
            updated_at=role.updated_at,
        )
        for role in user.roles
    ]
    
    return UserRolesResponse(
        user_id=user.id,
        roles=roles_list,
        permissions=user.get_all_permissions(),
    )


@router.post("/users/{user_id}/roles", response_model=UserRolesResponse, dependencies=[RequireAdmin])
async def assign_roles_to_user(
    user_id: UUID,
    data: AssignRolesToUser,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Assign roles to a user (replaces existing roles)."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get roles
    roles_result = await db.execute(
        select(Role).where(Role.id.in_(data.role_ids))
    )
    roles = roles_result.scalars().all()
    
    # Replace roles
    user.roles = roles
    user.updated_by = current_user.id
    
    await db.commit()
    await db.refresh(user)
    
    # Build response
    roles_list = [
        RoleListResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system_role=role.is_system_role,
            permission_count=len(role.permissions),
            created_at=role.created_at,
            updated_at=role.updated_at,
        )
        for role in user.roles
    ]
    
    return UserRolesResponse(
        user_id=user.id,
        roles=roles_list,
        permissions=user.get_all_permissions(),
    )


@router.delete("/users/{user_id}/roles/{role_id}", response_model=MessageResponse, dependencies=[RequireAdmin])
async def remove_role_from_user(
    user_id: UUID,
    role_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Remove a role from a user."""
    # Delete from association table
    await db.execute(
        sql_delete(user_roles).where(
            user_roles.c.user_id == user_id,
            user_roles.c.role_id == role_id
        )
    )
    await db.commit()
    
    return MessageResponse(message="Role removed from user")
