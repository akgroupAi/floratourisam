"""User service for user management."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import os
import shutil
from pathlib import Path

from fastapi import UploadFile, HTTPException, status
from app.core.config import settings

from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.user import UserAdminUpdate, UserCreate, UserUpdate
from app.utils.enums import UserRole

logger = get_logger(__name__)


class UserService:
    """Service for user operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID.

        Args:
            user_id: User UUID.

        Returns:
            User or None if not found.
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email.

        Args:
            email: User email.

        Returns:
            User or None if not found.
        """
        result = await self.db.execute(
            select(User).where(User.email == email, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        pagination: PaginationParams,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> tuple[List[User], int]:
        """Get paginated list of users.

        Args:
            pagination: Pagination parameters.
            role: Optional filter by role.
            is_active: Optional filter by active status.
            search: Optional search term.

        Returns:
            Tuple of (users, total count).
        """
        query = select(User).where(User.is_deleted == False)

        # Apply filters
        if role:
            query = query.where(User.role == role.value)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        if search:
            search_filter = f"%{search}%"
            query = query.where(
                (User.email.ilike(search_filter))
                | (User.full_name.ilike(search_filter))
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        if pagination.sort_by:
            sort_column = getattr(User, pagination.sort_by, User.created_at)
            if pagination.sort_order == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(User.created_at.desc())

        # Apply pagination
        query = query.offset(pagination.offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        users = result.scalars().all()

        return list(users), total

    async def create(self, data: UserCreate, created_by: Optional[UUID] = None) -> User:
        """Create a new user.

        Args:
            data: User creation data.
            created_by: ID of user creating this record.

        Returns:
            Created user.
        """
        user = User(
            email=data.email,
            hashed_password=get_password_hash(data.password),
            full_name=data.full_name,
            phone=data.phone,
            role=data.role.value,
            is_active=True,
            created_by=created_by,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info("user_created", user_id=str(user.id), email=user.email)

        return user

    async def update(
        self,
        user: User,
        data: UserUpdate,
        updated_by: Optional[UUID] = None,
    ) -> User:
        """Update user profile.

        Args:
            user: User to update.
            data: Update data.
            updated_by: ID of user making the update.

        Returns:
            Updated user.
        """
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(user, field, value)

        user.updated_by = updated_by
        user.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(user)

        logger.info("user_updated", user_id=str(user.id))

        return user

    async def admin_update(
        self,
        user: User,
        data: UserAdminUpdate,
        updated_by: UUID,
    ) -> User:
        """Admin update of user.

        Args:
            user: User to update.
            data: Admin update data.
            updated_by: Admin user ID.

        Returns:
            Updated user.
        """
        update_data = data.model_dump(exclude_unset=True)

        # Handle role conversion
        if "role" in update_data and update_data["role"]:
            update_data["role"] = update_data["role"].value

        for field, value in update_data.items():
            setattr(user, field, value)

        user.updated_by = updated_by
        user.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(user)

        logger.info("user_admin_updated", user_id=str(user.id), updated_by=str(updated_by))

        return user

    async def delete(self, user: User, deleted_by: UUID) -> bool:
        """Soft delete a user.

        Args:
            user: User to delete.
            deleted_by: ID of user deleting.

        Returns:
            True if successful.
        """
        user.soft_delete(deleted_by)
        await self.db.commit()

        logger.info("user_deleted", user_id=str(user.id), deleted_by=str(deleted_by))

        return True

    async def upload_avatar(self, user: User, file: UploadFile) -> User:
        """Upload user avatar.

        Args:
            user: User to update.
            file: Uploaded file.

        Returns:
            Updated user.
        """
        # Validate file type
        if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Only JPEG, PNG and WebP are allowed.",
            )

        # Validate file size
        file.file.seek(0, 2)
        size = file.file.tell()
        await file.seek(0)
        
        if size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size is {settings.MAX_UPLOAD_SIZE_MB}MB.",
            )

        # Create avatar directory
        avatar_dir = Path(settings.UPLOAD_DIR) / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        ext = file.filename.split(".")[-1] if file.filename else "jpg"
        filename = f"{user.id}.{ext}"
        file_path = avatar_dir / filename

        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Update user
        avatar_url = f"/static/uploads/avatars/{filename}"
        user.avatar_url = avatar_url
        user.updated_at = datetime.now(timezone.utc)
        user.updated_by = user.id

        await self.db.commit()
        await self.db.refresh(user)

        logger.info("avatar_uploaded", user_id=str(user.id), filename=filename)

        return user

    async def get_stats(self) -> dict:
        """Get user statistics.

        Returns:
            User statistics dictionary.
        """
        # Total users
        total_result = await self.db.execute(
            select(func.count()).select_from(User).where(User.is_deleted == False)
        )
        total_users = total_result.scalar() or 0

        # Active users
        active_result = await self.db.execute(
            select(func.count())
            .select_from(User)
            .where(User.is_deleted == False, User.is_active == True)
        )
        active_users = active_result.scalar() or 0

        # Verified users
        verified_result = await self.db.execute(
            select(func.count())
            .select_from(User)
            .where(User.is_deleted == False, User.is_verified == True)
        )
        verified_users = verified_result.scalar() or 0

        # Users by role
        role_result = await self.db.execute(
            select(User.role, func.count())
            .where(User.is_deleted == False)
            .group_by(User.role)
        )
        users_by_role = {role: count for role, count in role_result.all()}

        # New users today
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_result = await self.db.execute(
            select(func.count())
            .select_from(User)
            .where(User.is_deleted == False, User.created_at >= today_start)
        )
        new_users_today = today_result.scalar() or 0

        return {
            "total_users": total_users,
            "active_users": active_users,
            "verified_users": verified_users,
            "users_by_role": users_by_role,
            "new_users_today": new_users_today,
            "new_users_this_week": 0,  # Implement as needed
            "new_users_this_month": 0,  # Implement as needed
        }
