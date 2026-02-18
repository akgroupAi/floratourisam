"""Seed script for RBAC default roles and permissions."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.rbac import Role, Permission
from app.models.user import User
from app.core.security import get_password_hash
from app.utils.enums import UserRole


async def seed_rbac():
    """Seed default roles and permissions."""
    
    async with async_session_factory() as db:
        print("🌱 Seeding RBAC data...")
        
        # Define permissions
        permissions_data = [
            # User management
            {"name": "users.create", "resource": "users", "action": "create", "description": "Create new users"},
            {"name": "users.read", "resource": "users", "action": "read", "description": "View user details"},
            {"name": "users.update", "resource": "users", "action": "update", "description": "Update user information"},
            {"name": "users.delete", "resource": "users", "action": "delete", "description": "Delete users"},
            {"name": "users.manage", "resource": "users", "action": "manage", "description": "Full user management"},
            
            # Doctor management
            {"name": "doctors.create", "resource": "doctors", "action": "create", "description": "Create doctor profiles"},
            {"name": "doctors.read", "resource": "doctors", "action": "read", "description": "View doctor details"},
            {"name": "doctors.update", "resource": "doctors", "action": "update", "description": "Update doctor information"},
            {"name": "doctors.delete", "resource": "doctors", "action": "delete", "description": "Delete doctor profiles"},
            {"name": "doctors.manage", "resource": "doctors", "action": "manage", "description": "Full doctor management"},
            
            # Booking management
            {"name": "bookings.create", "resource": "bookings", "action": "create", "description": "Create bookings"},
            {"name": "bookings.read", "resource": "bookings", "action": "read", "description": "View booking details"},
            {"name": "bookings.update", "resource": "bookings", "action": "update", "description": "Update bookings"},
            {"name": "bookings.delete", "resource": "bookings", "action": "delete", "description": "Cancel bookings"},
            {"name": "bookings.manage", "resource": "bookings", "action": "manage", "description": "Full booking management"},
            
            # Consultation management
            {"name": "consultations.create", "resource": "consultations", "action": "create", "description": "Schedule consultations"},
            {"name": "consultations.read", "resource": "consultations", "action": "read", "description": "View consultations"},
            {"name": "consultations.update", "resource": "consultations", "action": "update", "description": "Update consultations"},
            {"name": "consultations.delete", "resource": "consultations", "action": "delete", "description": "Cancel consultations"},
            
            # Payment management
            {"name": "payments.read", "resource": "payments", "action": "read", "description": "View payment details"},
            {"name": "payments.manage", "resource": "payments", "action": "manage", "description": "Manage payments"},
            
            # Site content management
            {"name": "site.read", "resource": "site", "action": "read", "description": "View site content"},
            {"name": "site.update", "resource": "site", "action": "update", "description": "Update site content"},
            {"name": "site.manage", "resource": "site", "action": "manage", "description": "Full site content management"},
            
            # Dashboard access
            {"name": "dashboard.view", "resource": "dashboard", "action": "read", "description": "View admin dashboard"},
            
            # RBAC management
            {"name": "rbac.manage", "resource": "rbac", "action": "manage", "description": "Manage roles and permissions"},
        ]
        
        # Create permissions
        permissions = {}
        for perm_data in permissions_data:
            # Check if exists
            result = await db.execute(
                select(Permission).where(Permission.name == perm_data["name"])
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                perm = Permission(**perm_data)
                db.add(perm)
                await db.flush()
                permissions[perm_data["name"]] = perm
                print(f"  ✓ Created permission: {perm_data['name']}")
            else:
                permissions[perm_data["name"]] = existing
                print(f"  - Permission already exists: {perm_data['name']}")
        
        await db.commit()
        
        # Define roles with their permissions
        roles_data = [
            {
                "name": "SUPER_ADMIN",
                "description": "Super administrator with full system access",
                "is_system_role": True,
                "permissions": list(permissions.keys()),  # All permissions
            },
            {
                "name": "ADMIN",
                "description": "Administrator with management access",
                "is_system_role": True,
                "permissions": [
                    "users.read", "users.update",
                    "doctors.manage",
                    "bookings.manage",
                    "consultations.read", "consultations.update",
                    "payments.read",
                    "site.manage",
                    "dashboard.view",
                ],
            },
            {
                "name": "DOCTOR",
                "description": "Doctor role with consultation and patient management",
                "is_system_role": True,
                "permissions": [
                    "consultations.read", "consultations.update",
                    "bookings.read",
                    "patients.read",
                ],
            },
            {
                "name": "PATIENT",
                "description": "Patient role with basic access",
                "is_system_role": True,
                "permissions": [
                    "bookings.create", "bookings.read",
                    "consultations.create", "consultations.read",
                ],
            },
            {
                "name": "STAFF",
                "description": "Staff role with limited management access",
                "is_system_role": True,
                "permissions": [
                    "bookings.read", "bookings.update",
                    "consultations.read",
                    "site.read",
                ],
            },
        ]
        
        # Create roles
        for role_data in roles_data:
            # Check if exists
            result = await db.execute(
                select(Role).where(Role.name == role_data["name"])
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                role_perms = [permissions[p] for p in role_data["permissions"] if p in permissions]
                role = Role(
                    name=role_data["name"],
                    description=role_data["description"],
                    is_system_role=role_data["is_system_role"],
                    permissions=role_perms,
                )
                db.add(role)
                await db.flush()
                print(f"  ✓ Created role: {role_data['name']} with {len(role_perms)} permissions")
            else:
                print(f"  - Role already exists: {role_data['name']}")
        
        await db.commit()
        
        print("\n✅ RBAC seeding completed!")
        print("\nNext steps:")
        print("1. Run database migrations: alembic upgrade head")
        print("2. Create a super admin user via API or script")
        print("3. Assign roles to users via /rbac/users/{user_id}/roles endpoint")


if __name__ == "__main__":
    asyncio.run(seed_rbac())
