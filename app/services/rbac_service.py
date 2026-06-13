"""RBAC Service for managing roles, permissions, and assignments."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.rbac import Role, Permission, user_roles, role_permissions
from app.models.rbac_audit import RBACauditLog
from app.models.user import User
from app.models.hotel import Hotel
from app.models.apartment import Apartment
from app.models.restaurant import Restaurant
from app.schemas.rbac_api import (
    RoleCreate, RoleUpdate, RolePermissionsUpdate,
    UserRoleAssign, EntityManagerAssign
)

logger = get_logger(__name__)


class RBACService:
    """Service for RBAC operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============== ROLE MANAGEMENT ==============

    async def get_roles(self, page: int = 1, page_size: int = 50) -> Tuple[List[Role], int]:
        """Get all roles with user counts."""
        query = select(Role).where(Role.is_deleted == False).order_by(Role.name)
        
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query.options(selectinload(Role.permissions)))
        return result.scalars().all(), total

    async def get_role_by_id(self, role_id: UUID) -> Optional[Role]:
        """Get role by ID."""
        result = await self.db.execute(
            select(Role).where(Role.id == role_id, Role.is_deleted == False)
            .options(selectinload(Role.permissions), selectinload(Role.users))
        )
        return result.scalar_one_or_none()

    async def create_role(self, data: RoleCreate, actor_id: UUID) -> Role:
        """Create a new custom role."""
        role = Role(
            name=data.name,
            description=data.description,
            is_system_role=False,
            is_deleted=not data.is_active,
            created_by=actor_id
        )
        self.db.add(role)
        await self.db.flush()

        # Audit log
        await self._audit_log(
            actor_id=actor_id,
            action="create_role",
            target_type="role",
            target_id=role.id,
            target_name=data.name,
            description=f"Created role: {data.name}",
            metadata={"is_active": data.is_active}
        )

        await self.db.commit()
        return role

    async def update_role(self, role_id: UUID, data: RoleUpdate, actor_id: UUID) -> Optional[Role]:
        """Update role (blocks system roles)."""
        role = await self.get_role_by_id(role_id)
        if not role:
            return None

        if role.is_system_role:
            raise ValueError("Cannot modify system roles")

        changes = {}
        if data.label is not None and data.label != role.name:
            changes["label"] = (role.name, data.label)
            role.name = data.label

        if data.description is not None and data.description != role.description:
            changes["description"] = (role.description, data.description)
            role.description = data.description

        if data.is_active is not None and data.is_active != role.is_deleted:
            changes["is_active"] = (not role.is_deleted, data.is_active)
            role.is_deleted = not data.is_active

        role.updated_by = actor_id
        await self.db.commit()

        # Audit log
        await self._audit_log(
            actor_id=actor_id,
            action="update_role",
            target_type="role",
            target_id=role.id,
            target_name=role.name,
            description=f"Updated role: {role.name}",
            metadata={"changes": changes}
        )

        return role

    async def delete_role(self, role_id: UUID, actor_id: UUID) -> bool:
        """Delete custom role (blocks system roles and roles with users)."""
        role = await self.get_role_by_id(role_id)
        if not role:
            return False

        if role.is_system_role:
            raise ValueError("Cannot delete system roles")

        # Check if role has users
        result = await self.db.execute(
            select(func.count()).select_from(user_roles).where(user_roles.c.role_id == role_id)
        )
        user_count = result.scalar() or 0
        if user_count > 0:
            raise ValueError(f"Cannot delete role with {user_count} assigned users")

        role.is_deleted = True
        role.deleted_by = actor_id
        await self.db.commit()

        # Audit log
        await self._audit_log(
            actor_id=actor_id,
            action="delete_role",
            target_type="role",
            target_id=role.id,
            target_name=role.name,
            description=f"Deleted role: {role.name}"
        )

        return True

    # ============== PERMISSION MANAGEMENT ==============

    async def get_role_permissions(self, role_id: UUID) -> Optional[Dict]:
        """Get permissions matrix for a role."""
        role_exists = await self.db.scalar(
            select(func.count(Role.id)).where(Role.id == role_id, Role.is_deleted == False)
        )
        if not role_exists:
            return None

        # Query directly from DB — bypasses ORM identity-map cache which can be
        # stale after raw-SQL inserts in update_role_permissions.
        result = await self.db.execute(
            select(Permission)
            .join(role_permissions, role_permissions.c.permission_id == Permission.id)
            .where(role_permissions.c.role_id == role_id)
        )
        perms = result.scalars().all()

        matrix = {}
        for perm in perms:
            if perm.resource not in matrix:
                matrix[perm.resource] = {
                    "can_create": False,
                    "can_read": False,
                    "can_update": False,
                    "can_delete": False,
                }
            if perm.action == "create":
                matrix[perm.resource]["can_create"] = True
            elif perm.action == "read":
                matrix[perm.resource]["can_read"] = True
            elif perm.action == "update":
                matrix[perm.resource]["can_update"] = True
            elif perm.action == "delete":
                matrix[perm.resource]["can_delete"] = True

        return matrix

    async def update_role_permissions(
        self, role_id: UUID, data: RolePermissionsUpdate, actor_id: UUID
    ) -> bool:
        """Update permissions matrix for a role."""
        try:
            # Verify role exists (scalar only — don't load permissions relationship)
            role_result = await self.db.execute(
                select(Role).where(Role.id == role_id, Role.is_deleted == False)
            )
            role = role_result.scalar_one_or_none()
            if not role:
                return False

            # Delete all existing permissions via raw SQL
            await self.db.execute(
                role_permissions.delete().where(role_permissions.c.role_id == role_id)
            )

            # Insert new permissions via raw SQL (avoids stale ORM collection cache)
            for resource, actions in data.permissions.items():
                for action, enabled in actions.items():
                    if enabled:
                        action_name = action.replace("can_", "")  # can_create → create
                        perm_result = await self.db.execute(
                            select(Permission).where(
                                Permission.resource == resource,
                                Permission.action == action_name
                            )
                        )
                        permission = perm_result.scalar_one_or_none()
                        if permission:
                            await self.db.execute(
                                role_permissions.insert().values(
                                    role_id=role_id,
                                    permission_id=permission.id
                                )
                            )

            # Update role timestamp via raw SQL to stay consistent
            await self.db.execute(
                sql_update(Role)
                .where(Role.id == role_id)
                .values(updated_by=actor_id, updated_at=datetime.utcnow())
            )

            # Capture scalars before expiring to avoid MissingGreenlet on attribute access.
            role_id_val = role.id
            role_name_val = role.name

            # Expire the role so the ORM's stale permissions cache is discarded.
            self.db.expire(role)
            await self.db.commit()

            await self._audit_log(
                actor_id=actor_id,
                action="update_permissions",
                target_type="role",
                target_id=role_id_val,
                target_name=role_name_val,
                description=f"Updated permissions for role: {role_name_val}",
                meta_data={"permissions": data.permissions, "scope_own_only": data.scope_own_only}
            )
            await self.db.commit()

            return True
        except Exception as e:
            logger.error(f"Error updating permissions for role {role_id}: {str(e)}")
            await self.db.rollback()
            raise

    # ============== USER ROLE ASSIGNMENT ==============

    async def assign_role_to_user(self, data: UserRoleAssign, actor_id: UUID) -> Optional[User]:
        """Assign role to user."""
        # Find user
        user = None
        if data.user_id:
            user = await self.db.execute(
                select(User).where(User.id == data.user_id)
            )
            user = user.scalar_one_or_none()
        elif data.email:
            user = await self.db.execute(
                select(User).where(User.email == data.email)
            )
            user = user.scalar_one_or_none()

        if not user:
            return None

        # Find role
        role = await self.get_role_by_id(data.role_id)
        if not role:
            return None

        # Check if already assigned
        existing = await self.db.execute(
            select(user_roles).where(
                user_roles.c.user_id == user.id,
                user_roles.c.role_id == data.role_id
            )
        )
        if existing.scalar_one_or_none():
            logger.info(f"User {user.email} already has role {role.name}")
            return user

        # Assign role
        stmt = user_roles.insert().values(user_id=user.id, role_id=data.role_id)
        await self.db.execute(stmt)
        await self.db.commit()

        # Audit log
        await self._audit_log(
            actor_id=actor_id,
            action="assign_role",
            target_type="user",
            target_id=user.id,
            target_name=user.email,
            description=f"Assigned role '{role.name}' to {user.email}",
            metadata={"role_name": role.name, "role_id": str(data.role_id)}
        )

        logger.info(f"Assigned role {role.name} to user {user.email}")
        return user

    async def remove_role_from_user(self, user_id: UUID, role_id: UUID, actor_id: UUID) -> bool:
        """Remove role from user."""
        # Check if assignment exists
        existing = await self.db.execute(
            select(user_roles).where(
                user_roles.c.user_id == user_id,
                user_roles.c.role_id == role_id
            )
        )
        if not existing.scalar_one_or_none():
            return False

        await self.db.execute(
            user_roles.delete().where(
                user_roles.c.user_id == user_id,
                user_roles.c.role_id == role_id
            )
        )
        await self.db.commit()

        # Get user and role info for audit
        user = await self.db.execute(select(User).where(User.id == user_id))
        user_obj = user.scalar_one_or_none()
        role = await self.get_role_by_id(role_id)

        # Audit log
        await self._audit_log(
            actor_id=actor_id,
            action="remove_role",
            target_type="user",
            target_id=user_id,
            target_name=user_obj.email if user_obj else None,
            description=f"Removed role '{role.name}' from {user_obj.email if user_obj else 'deleted user'}",
            metadata={"role_name": role.name if role else None}
        )

        return True

    async def get_user_with_resources(self, user_id: UUID):
        """Get user with their assigned resources."""
        result = await self.db.execute(
            select(User).where(User.id == user_id).options(selectinload(User.roles))
        )
        user = result.scalar_one_or_none()
        if not user:
            return None

        resources = {"hotels": [], "apartments": [], "restaurants": []}

        # Get assigned resources based on roles
        for role in user.roles:
            if role.name == "hotel_manager":
                hotels = await self.db.execute(
                    select(Hotel).where(
                        Hotel.manager_id == user_id,
                        Hotel.is_deleted == False
                    )
                )
                resources["hotels"] = [
                    {"id": str(h.id), "name": h.name, "city": h.city, "country": h.country}
                    for h in hotels.scalars().all()
                ]
            elif role.name == "apartment_manager":
                apts = await self.db.execute(
                    select(Apartment).where(
                        Apartment.manager_id == user_id,
                        Apartment.is_deleted == False
                    )
                )
                resources["apartments"] = [
                    {"id": str(a.id), "name": a.name, "city": a.city, "country": a.country}
                    for a in apts.scalars().all()
                ]
            elif role.name == "restaurant_manager":
                rests = await self.db.execute(
                    select(Restaurant).where(
                        Restaurant.manager_id == user_id,
                        Restaurant.is_deleted == False
                    )
                )
                resources["restaurants"] = [
                    {"id": str(r.id), "name": r.name, "city": r.city, "country": r.country}
                    for r in rests.scalars().all()
                ]

        return {"user": user, "resources": resources}

    # ============== AUDIT LOGGING ==============

    async def _audit_log(
        self,
        actor_id: UUID,
        action: str,
        target_type: str,
        target_id: Optional[UUID] = None,
        target_name: Optional[str] = None,
        description: Optional[str] = None,
        meta_data: Optional[dict] = None
    ) -> None:
        """Log RBAC action to audit log."""
        # Get actor info
        actor = await self.db.execute(select(User).where(User.id == actor_id))
        actor_obj = actor.scalar_one_or_none()

        log_entry = RBACauditLog(
            actor_user_id=actor_id,
            actor_email=actor_obj.email if actor_obj else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            description=description,
            meta_data=meta_data
        )
        self.db.add(log_entry)

    async def get_audit_logs(
        self, limit: int = 50, offset: int = 0
    ) -> Tuple[List[RBACauditLog], int]:
        """Get recent audit logs."""
        query = select(RBACauditLog).order_by(RBACauditLog.created_at.desc())

        count_result = await self.db.execute(
            select(func.count()).select_from(RBACauditLog)
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            query.limit(limit).offset(offset)
        )
        return result.scalars().all(), total

    # ============== STATS ==============

    async def get_rbac_stats(self) -> dict:
        """Get RBAC dashboard statistics."""
        # Total roles
        roles_result = await self.db.execute(
            select(func.count(Role.id)).where(Role.is_deleted == False)
        )
        total_roles = roles_result.scalar() or 0

        # Assigned users (distinct users with at least one role)
        assigned_result = await self.db.execute(
            select(func.count(func.distinct(user_roles.c.user_id)))
        )
        assigned_users = assigned_result.scalar() or 0

        # Admin users (super_admin or admin)
        admin_result = await self.db.execute(
            select(func.count(User.id)).where(
                User.is_deleted == False,
                User.role.in_(["super_admin", "admin"])
            )
        )
        admin_users = admin_result.scalar() or 0

        # Entities with managers
        hotels_mgr = await self.db.execute(
            select(func.count(Hotel.id)).where(
                Hotel.is_deleted == False,
                Hotel.manager_id.isnot(None)
            )
        )
        hotels_with_manager = hotels_mgr.scalar() or 0

        apts_mgr = await self.db.execute(
            select(func.count(Apartment.id)).where(
                Apartment.is_deleted == False,
                Apartment.manager_id.isnot(None)
            )
        )
        apartments_with_manager = apts_mgr.scalar() or 0

        rests_mgr = await self.db.execute(
            select(func.count(Restaurant.id)).where(
                Restaurant.is_deleted == False,
                Restaurant.manager_id.isnot(None)
            )
        )
        restaurants_with_manager = rests_mgr.scalar() or 0

        return {
            "total_roles": total_roles,
            "assigned_users": assigned_users,
            "admin_users": admin_users,
            "hotels_with_manager": hotels_with_manager,
            "apartments_with_manager": apartments_with_manager,
            "restaurants_with_manager": restaurants_with_manager
        }
