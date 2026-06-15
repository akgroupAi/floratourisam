"""RBAC Management API Endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.rbac_api import (
    RoleCreate, RoleUpdate, RolePermissionsUpdate,
    RoleResponse, RoleDetailResponse,
    UserRoleAssign, UserWithRoleResponse,
    RBACStatsResponse, AuditLogListResponse, AuditLogResponse,
    ManagerListResponse, EntityWithManagerResponse,
    EntityManagerAssign
)
from app.services.rbac_service import RBACService
from app.utils.enums import UserRole
from app.models.hotel import Hotel
from app.models.apartment import Apartment
from app.models.restaurant import Restaurant

logger = get_logger(__name__)
router = APIRouter(prefix="/admin/rbac", tags=["RBAC Management"], dependencies=[RequireAdmin])


# ============== STATS & DASHBOARD ==============

@router.get("/stats", response_model=RBACStatsResponse)
async def get_rbac_stats(db: DatabaseSession):
    """Get RBAC dashboard statistics."""
    service = RBACService(db)
    stats = await service.get_rbac_stats()
    return RBACStatsResponse(**stats)


# ============== ROLES ==============

@router.get("/roles", response_model=PaginatedResponse[RoleResponse])
async def list_roles(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """List all roles."""
    service = RBACService(db)
    roles, total = await service.get_roles(page, page_size)
    
    # Count users per role
    items = []
    for role in roles:
        result = await db.execute(
            select(User).where(User.role == role.name)
        )
        users_count = len(result.scalars().all())
        
        items.append(RoleResponse(
            id=role.id,
            name=role.name,
            label=role.name if not role.description else role.description.split("\n")[0],
            description=role.description,
            is_system_role=role.is_system_role,
            is_active=not role.is_deleted,
            users_count=users_count,
            scope_own_only=False,  # TODO: Add to model
            created_at=role.created_at,
            updated_at=role.updated_at
        ))
    
    return PaginatedResponse.create(items, total, page, page_size)


@router.get("/roles/{role_id}", response_model=RoleDetailResponse)
async def get_role(role_id: UUID, db: DatabaseSession):
    """Get role with permissions matrix."""
    service = RBACService(db)
    role = await service.get_role_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    permissions = await service.get_role_permissions(role_id)
    
    # Count users
    result = await db.execute(
        select(User).where(User.role == role.name)
    )
    users_count = len(result.scalars().all())
    
    return RoleDetailResponse(
        id=role.id,
        name=role.name,
        label=role.name,
        description=role.description,
        is_system_role=role.is_system_role,
        is_active=not role.is_deleted,
        users_count=users_count,
        scope_own_only=False,
        created_at=role.created_at,
        updated_at=role.updated_at,
        permissions=permissions or {}
    )


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a new role (custom roles only)."""
    service = RBACService(db)
    try:
        role = await service.create_role(data, current_user.id)
        await db.refresh(role)
        return RoleResponse(
            id=role.id,
            name=role.name,
            label=data.label,
            description=role.description,
            is_system_role=role.is_system_role,
            is_active=not role.is_deleted,
            users_count=0,
            scope_own_only=False,
            created_at=role.created_at,
            updated_at=role.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    data: RoleUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update role details."""
    service = RBACService(db)
    try:
        role = await service.update_role(role_id, data, current_user.id)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        
        await db.refresh(role)
        return RoleResponse(
            id=role.id,
            name=role.name,
            label=role.name,
            description=role.description,
            is_system_role=role.is_system_role,
            is_active=not role.is_deleted,
            users_count=0,
            scope_own_only=False,
            created_at=role.created_at,
            updated_at=role.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/roles/{role_id}", response_model=MessageResponse)
async def delete_role(
    role_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Delete a custom role."""
    service = RBACService(db)
    try:
        deleted = await service.delete_role(role_id, current_user.id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Role not found")
        return MessageResponse(message="Role deleted successfully")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== PERMISSIONS ==============

@router.get("/permissions")
async def list_permissions(db: DatabaseSession):
    """List all available permissions."""
    from app.models.rbac import Permission
    result = await db.execute(
        select(Permission).where(Permission.is_deleted == False).order_by(Permission.resource, Permission.action)
    )
    perms = result.scalars().all()
    return [
        {"id": str(p.id), "name": p.name, "resource": p.resource, "action": p.action, "description": p.description}
        for p in perms
    ]


@router.get("/roles/{role_id}/permissions")
async def get_role_permissions(role_id: UUID, db: DatabaseSession):
    """Get permissions matrix for a role."""
    service = RBACService(db)
    permissions = await service.get_role_permissions(role_id)
    if permissions is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"role_id": str(role_id), "permissions": permissions}


@router.put("/roles/{role_id}/permissions", response_model=MessageResponse)
async def update_role_permissions(
    role_id: UUID,
    data: RolePermissionsUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update permissions matrix for a role."""
    service = RBACService(db)
    updated = await service.update_role_permissions(role_id, data, current_user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Role not found")
    return MessageResponse(message="Permissions updated successfully")


# ============== USER ROLE ASSIGNMENTS ==============

@router.get("/user-roles", response_model=PaginatedResponse[UserWithRoleResponse])
async def list_user_roles(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List users with their roles and assigned resources (excluding patients and doctors)."""
    # Exclude patient and doctor roles
    query = select(User).where(
        User.is_deleted == False,
        User.role.not_in([UserRole.PATIENT.value, UserRole.DOCTOR.value])
    ).order_by(User.email)
    
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.is_deleted == False,
            User.role.not_in([UserRole.PATIENT.value, UserRole.DOCTOR.value])
        )
    )
    total = count_result.scalar() or 0
    
    result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )
    users = result.scalars().all()
    
    service = RBACService(db)
    items = []
    for user in users:
        user_data = await service.get_user_with_resources(user.id)
        if user_data:
            items.append(UserWithRoleResponse(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                role_label=user.role.replace("_", " ").title(),
                assigned_resources=user_data["resources"],
                assigned_at=user.created_at
            ))
    
    return PaginatedResponse.create(items, total, page, page_size)


@router.post("/user-roles", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def assign_role_to_user(
    data: UserRoleAssign,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Assign role to user."""
    service = RBACService(db)
    user = await service.assign_role_to_user(data, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return MessageResponse(message=f"Role assigned to {user.email}")


@router.delete("/user-roles/{user_id}/{role_id}", response_model=MessageResponse)
async def remove_role_from_user(
    user_id: UUID,
    role_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Remove role from user."""
    service = RBACService(db)
    removed = await service.remove_role_from_user(user_id, role_id, current_user.id)
    if not removed:
        raise HTTPException(status_code=404, detail="User-role assignment not found")
    return MessageResponse(message="Role removed from user")


@router.patch("/user-roles/{user_id}", response_model=MessageResponse)
async def update_user_role(
    user_id: UUID,
    data: UserRoleAssign,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Update a user's role (change old role to new role).
    
    Powers the "Manage" dialog in Tab 2 to change user's role.
    Request body should contain 'role_id' (UUID) to change to.
    """
    service = RBACService(db)
    
    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Verify new role exists and get its name
        new_role = await service.get_role_by_id(data.role_id)
        if not new_role:
            raise HTTPException(status_code=404, detail="Role not found")
        
        # Don't allow changing to same role
        if user.role == new_role.name:
            raise HTTPException(status_code=400, detail="User already has this role")
        
        # Update user role to new role name
        user.role = new_role.name
        user.updated_by = current_user.id
        user.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(user)
        
        # Log the change to audit
        await service._audit_log(
            actor_id=current_user.id,
            action="update_user_role",
            target_type="user",
            target_id=user.id,
            target_name=user.email,
            meta_data={
                "old_role": user.role if user.role != new_role.name else None,
                "new_role": new_role.name,
                "role_id": str(data.role_id)
            },
            description=f"Changed user role to {new_role.name}"
        )
        
        return MessageResponse(message=f"User role updated to {new_role.name}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/{user_id}/resources", response_model=UserWithRoleResponse)
async def get_user_resources(user_id: UUID, db: DatabaseSession):
    """Get all resources assigned to a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    service = RBACService(db)
    user_data = await service.get_user_with_resources(user_id)
    
    return UserWithRoleResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        role_label=user.role.replace("_", " ").title(),
        assigned_resources=user_data["resources"],
        assigned_at=user.created_at
    )


# ============== MANAGERS FOR ASSIGNMENT DIALOGS ==============

@router.get("/managers", response_model=list[ManagerListResponse])
async def get_available_managers(
    role: Optional[str] = Query(None, description="Filter by role: hotel_manager, apartment_manager, restaurant_manager"),
    db: DatabaseSession = None,
):
    """Get available managers for assignment."""
    query = select(User).where(User.is_deleted == False, User.is_active == True)
    
    if role:
        query = query.where(User.role == role)
    else:
        # Get all manager roles
        query = query.where(
            User.role.in_([
                UserRole.HOTEL_MANAGER.value,
                UserRole.APARTMENT_MANAGER.value,
                UserRole.RESTAURANT_MANAGER.value
            ])
        )
    
    result = await db.execute(query.order_by(User.email))
    users = result.scalars().all()
    
    # Count assigned resources for each manager
    service = RBACService(db)
    managers = []
    for user in users:
        user_data = await service.get_user_with_resources(user.id)
        assigned_count = (
            len(user_data["resources"]["hotels"]) +
            len(user_data["resources"]["apartments"]) +
            len(user_data["resources"]["restaurants"])
        )
        managers.append(ManagerListResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            assigned_count=assigned_count
        ))
    
    return managers


# ============== AUDIT LOGS ==============

@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    db: DatabaseSession,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get recent RBAC audit logs."""
    service = RBACService(db)
    logs, total = await service.get_audit_logs(limit, offset)
    
    items = [
        AuditLogResponse(**log.__dict__)
        for log in logs
    ]
    
    return AuditLogListResponse(
        items=items,
        total=total,
        page=offset // limit + 1,
        page_size=limit
    )
