"""Dependency injection for database sessions, authentication, and RBAC."""

from typing import Annotated, List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db_session
from app.models.user import User
from app.utils.enums import UserRole

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async for session in get_db_session():
        yield session


# Type alias for database session dependency
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_optional(
    db: DatabaseSession,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(security)
    ] = None,
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None."""
    if credentials is None:
        return None

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    # Fetch user from database
    from app.services.user_service import UserService

    user_service = UserService(db)
    user = await user_service.get_by_id(user_id)

    if user is None or not user.is_active:
        return None

    return user


async def get_current_user(
    db: DatabaseSession,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(security)
    ] = None,
) -> User:
    """Get current authenticated user. Raises if not authenticated."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    from app.services.user_service import UserService

    user_service = UserService(db)
    user = await user_service.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


# Type alias for current user dependency
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_current_user_optional)]


def require_roles(allowed_roles: List[UserRole]):
    """Dependency factory for role-based access control.

    Args:
        allowed_roles: List of roles that are allowed to access the endpoint.

    Returns:
        Dependency function that checks user role.
    """

    async def role_checker(current_user: CurrentUser) -> User:
        if current_user.role not in [role.value for role in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}",
            )
        return current_user

    return role_checker


def require_any_role(*roles: UserRole):
    """Shorthand dependency for requiring any of the specified roles."""
    return Depends(require_roles(list(roles)))


# Pre-configured role dependencies
RequireSuperAdmin = Depends(require_roles([UserRole.SUPER_ADMIN]))
RequireAdmin = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))
RequireDoctor = Depends(
    require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.DOCTOR])
)
RequirePatient = Depends(
    require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.PATIENT])
)
RequireHotelManager = Depends(
    require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HOTEL_MANAGER])
)
RequireApartmentManager = Depends(
    require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.APARTMENT_MANAGER])
)
RequireRestaurantManager = Depends(
    require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.RESTAURANT_MANAGER])
)
# Admins plus any entity manager — used by endpoints whose data is scoped per manager
RequireAdminOrManager = Depends(
    require_roles([
        UserRole.SUPER_ADMIN,
        UserRole.ADMIN,
        UserRole.HOTEL_MANAGER,
        UserRole.APARTMENT_MANAGER,
        UserRole.RESTAURANT_MANAGER,
    ])
)


async def get_current_active_superuser(current_user: CurrentUser) -> User:
    """Dependency to ensure user is a superuser."""
    if current_user.role != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


SuperUser = Annotated[User, Depends(get_current_active_superuser)]


async def get_current_patient(
    current_user: CurrentUser,
    db: DatabaseSession,
) -> "Patient":
    """Get current patient profile. Creates one if it doesn't exist."""
    from app.services.patient_service import PatientService

    # Allow Patients and Admins
    allowed_roles = [UserRole.PATIENT.value, UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access patient profile",
        )

    # Get or create patient profile
    service = PatientService(db)
    return await service.get_or_create(current_user.id)
