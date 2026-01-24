"""API dependencies."""

from app.core.dependencies import (
    CurrentUser,
    DatabaseSession,
    OptionalUser,
    RequireAdmin,
    RequireDoctor,
    RequireHotelManager,
    RequirePatient,
    RequireRestaurantManager,
    RequireSuperAdmin,
    SuperUser,
    get_current_user,
    get_current_user_optional,
    get_db,
    require_roles,
)

__all__ = [
    "CurrentUser",
    "DatabaseSession",
    "OptionalUser",
    "RequireAdmin",
    "RequireDoctor",
    "RequireHotelManager",
    "RequirePatient",
    "RequireRestaurantManager",
    "RequireSuperAdmin",
    "SuperUser",
    "get_current_user",
    "get_current_user_optional",
    "get_db",
    "require_roles",
]
