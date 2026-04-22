"""Resource-based authorization utilities for entity-scoped access control."""

from uuid import UUID
from typing import Optional, Type, TypeVar
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.utils.enums import UserRole
from app.models.user import User
from app.models.hotel import Hotel
from app.models.apartment import Apartment
from app.models.restaurant import Restaurant

T = TypeVar('T', Hotel, Apartment, Restaurant)


class ResourceAuthError(HTTPException):
    """Raised when user doesn't have access to a resource."""
    
    def __init__(self, detail: str = "You don't have access to this resource"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


async def check_resource_access(
    resource_id: UUID,
    resource_model: Type[T],
    current_user: User,
    db: AsyncSession,
) -> T:
    """
    Check if user has access to a specific resource.
    
    Rules:
    - Super Admin / Admin: Can access any resource
    - Hotel/Apartment/Restaurant Manager: Can only access their assigned resource
    - Other roles: No access
    
    Args:
        resource_id: The resource ID to check access for
        resource_model: The model class (Hotel, Apartment, or Restaurant)
        current_user: The authenticated user
        db: Database session
        
    Returns:
        The resource object if access is granted
        
    Raises:
        HTTPException: If resource not found or access denied
    """
    # Fetch the resource
    result = await db.execute(
        select(resource_model).where(
            resource_model.id == resource_id,
            resource_model.is_deleted == False
        )
    )
    resource = result.scalar_one_or_none()
    
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_model.__name__} not found"
        )
    
    # Super Admin / Admin can access any resource
    if current_user.role in [UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value]:
        return resource
    
    # Manager roles: check if resource is assigned to them
    manager_role_map = {
        UserRole.HOTEL_MANAGER.value: "hotel_manager",
        UserRole.APARTMENT_MANAGER.value: "apartment_manager",
        UserRole.RESTAURANT_MANAGER.value: "restaurant_manager",
    }
    
    if current_user.role in manager_role_map:
        if resource.manager_id != current_user.id:
            raise ResourceAuthError(
                detail=f"You don't have access to this {resource_model.__name__}"
            )
        return resource
    
    # All other roles are denied
    raise ResourceAuthError(
        detail=f"No permission to access {resource_model.__name__}"
    )


async def filter_resources_by_user(
    resource_model: Type[T],
    current_user: User,
    query = None,
) -> any:
    """
    Filter a query to only include resources the user has access to.
    
    Args:
        resource_model: The model class to filter
        current_user: The authenticated user
        query: Optional existing query to filter (if None, creates new one)
        
    Returns:
        Filtered query
    """
    if query is None:
        query = select(resource_model)
    
    # Super Admin / Admin see all resources
    if current_user.role in [UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value]:
        return query
    
    # Managers see only their assigned resources
    if current_user.role in [
        UserRole.HOTEL_MANAGER.value,
        UserRole.APARTMENT_MANAGER.value,
        UserRole.RESTAURANT_MANAGER.value,
    ]:
        return query.where(resource_model.manager_id == current_user.id)
    
    # All other roles see nothing
    return query.where(resource_model.id == None)  # Returns empty result
