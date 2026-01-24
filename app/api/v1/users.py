"""User management endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.user import (
    UserAdminUpdate, UserCreate, UserListResponse,
    UserProfileResponse, UserResponse, UserStatsResponse, UserUpdate,
)
from app.services.user_service import UserService
from app.utils.enums import UserRole

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user(current_user: CurrentUser):
    """Get current user profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(data: UserUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update current user profile."""
    service = UserService(db)
    return await service.update(current_user, data, current_user.id)


@router.get("", response_model=PaginatedResponse[UserListResponse], dependencies=[RequireAdmin])
async def list_users(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
):
    """List users (admin only)."""
    service = UserService(db)
    pagination = PaginationParams(page=page, page_size=page_size)
    users, total = await service.get_list(pagination, role, is_active, search)
    return PaginatedResponse.create(users, total, page, page_size)


@router.post("", response_model=UserResponse, dependencies=[RequireAdmin])
async def create_user(data: UserCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new user (admin only)."""
    service = UserService(db)
    existing = await service.get_by_email(data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    return await service.create(data, current_user.id)


@router.get("/stats", response_model=UserStatsResponse, dependencies=[RequireAdmin])
async def get_user_stats(db: DatabaseSession):
    """Get user statistics (admin only)."""
    service = UserService(db)
    return await service.get_stats()


@router.get("/{user_id}", response_model=UserProfileResponse, dependencies=[RequireAdmin])
async def get_user(user_id: UUID, db: DatabaseSession):
    """Get user by ID (admin only)."""
    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse, dependencies=[RequireAdmin])
async def update_user(user_id: UUID, data: UserAdminUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update user (admin only)."""
    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await service.admin_update(user, data, current_user.id)


@router.delete("/{user_id}", dependencies=[RequireAdmin])
async def delete_user(user_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete user (admin only)."""
    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await service.delete(user, current_user.id)
    return {"message": "User deleted"}
