"""Authentication service."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.utils.enums import UserRole
from app.utils.helpers import generate_token

logger = get_logger(__name__)


class AuthService:
    """Service for authentication operations."""

    # Roles allowed to use the admin panel login
    ADMIN_PORTAL_ROLES = {
        UserRole.SUPER_ADMIN.value,
        UserRole.ADMIN.value,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(
        self,
        request: LoginRequest,
        *,
        portal: str = "public",
    ) -> Optional[AuthResponse]:
        """Authenticate user and return tokens.

        Args:
            request: Login request with email and password.
            portal: ``public`` (website) or ``admin`` (admin panel).
                - public: rejects admin/super_admin so they cannot enter the
                  public site session and get redirected to admin dashboard.
                - admin: only allows admin/super_admin.

        Returns:
            Auth response with user info and tokens, or None if invalid.
        """
        from sqlalchemy.orm import selectinload

        # Find user by email with roles
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.email == request.email, User.is_deleted == False)
        )
        user = result.scalar_one_or_none()

        if user is None:
            logger.warning("login_failed", reason="user_not_found", email=request.email)
            return None

        if not verify_password(request.password, user.hashed_password):
            logger.warning("login_failed", reason="invalid_password", email=request.email)
            return None

        if not user.is_active:
            logger.warning("login_failed", reason="user_inactive", email=request.email)
            return None

        is_admin_user = user.role in self.ADMIN_PORTAL_ROLES

        if portal == "admin" and not is_admin_user:
            logger.warning(
                "login_failed",
                reason="not_admin_portal",
                email=request.email,
                role=user.role,
            )
            raise PermissionError(
                "This account is not allowed to access the admin panel. "
                "Please use the public website login."
            )

        if portal == "public" and is_admin_user:
            logger.warning(
                "login_failed",
                reason="admin_on_public_portal",
                email=request.email,
                role=user.role,
            )
            raise PermissionError(
                "Admin accounts must sign in via the admin login. "
                "Use POST /api/v1/auth/admin/login or the admin panel."
            )

        # Generate tokens (portal claim helps frontends isolate sessions)
        access_token = create_access_token(
            subject=str(user.id),
            additional_claims={
                "role": user.role,
                "email": user.email,
                "portal": portal,
            },
        )
        refresh_token = create_refresh_token(subject=str(user.id))

        # Update last login
        user.last_login = datetime.now(timezone.utc)
        user.refresh_token = refresh_token
        await self.db.commit()

        logger.info(
            "login_success",
            user_id=str(user.id),
            email=user.email,
            portal=portal,
        )

        # Get role names and permissions
        role_names = [role.name for role in user.roles]
        permissions = user.get_all_permissions()

        return AuthResponse(
            user_id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_verified=user.is_verified,
            is_admin=user.is_admin,
            roles=role_names,
            permissions=permissions,
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=30 * 60,  # 30 minutes in seconds
            ),
        )

    async def register(self, request: RegisterRequest) -> Optional[User]:
        """Register a new user.

        Args:
            request: Registration request.

        Returns:
            Created user or None if email already exists.
        """
        # Check if email already exists
        result = await self.db.execute(
            select(User).where(User.email == request.email)
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.warning("registration_failed", reason="email_exists", email=request.email)
            return None

        # Create user
        user = User(
            email=request.email,
            hashed_password=get_password_hash(request.password),
            full_name=request.full_name,
            phone=request.phone,
            role=request.role.value,
            is_active=True,
            is_verified=False,
            verification_token=generate_token(),
        )

        self.db.add(user)
        await self.db.flush()  # Flush to get user.id before creating profile

        # Create role-specific profile
        if request.role.value == UserRole.DOCTOR.value:
            from app.models.doctor import Doctor
            
            # Create doctor profile with placeholder license number
            doctor = Doctor(
                user_id=user.id,
                license_number=None,  # Will be updated later by the doctor
                created_by=user.id,
            )
            self.db.add(doctor)
            logger.info("doctor_profile_created", user_id=str(user.id))
            
        elif request.role.value == UserRole.PATIENT.value:
            from app.models.patient import Patient
            
            # Create patient profile
            patient = Patient(
                user_id=user.id,
                created_by=user.id,
            )
            self.db.add(patient)
            logger.info("patient_profile_created", user_id=str(user.id))

        await self.db.commit()
        await self.db.refresh(user)

        # Send verification email
        from app.utils.email_sender import send_email, render_verification_email_html
        
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={user.verification_token}"
        
        email_html = render_verification_email_html(
            full_name=user.full_name,
            verification_url=verification_url
        )
        
        await send_email(
            db=self.db,
            to_email=user.email,
            to_name=user.full_name,
            subject="Verify your email - Medical Tourism Platform",
            body_html=email_html,
            category="verification",
            user_id=user.id
        )

        logger.info("user_registered", user_id=str(user.id), email=user.email, role=user.role)

        return user


    async def refresh_tokens(self, refresh_token: str) -> Optional[TokenResponse]:
        """Refresh access token using refresh token.

        Args:
            refresh_token: Current refresh token.

        Returns:
            New token pair or None if invalid.
        """
        user_id = verify_token(refresh_token, token_type="refresh")
        if user_id is None:
            logger.warning("token_refresh_failed", reason="invalid_token")
            return None

        # Find user
        result = await self.db.execute(
            select(User).where(
                User.id == UUID(user_id),
                User.refresh_token == refresh_token,
                User.is_active == True,
                User.is_deleted == False,
            )
        )
        user = result.scalar_one_or_none()

        if user is None:
            logger.warning("token_refresh_failed", reason="user_not_found", user_id=user_id)
            return None

        # Generate new tokens
        access_token = create_access_token(
            subject=str(user.id),
            additional_claims={"role": user.role, "email": user.email},
        )
        new_refresh_token = create_refresh_token(subject=str(user.id))

        # Update refresh token
        user.refresh_token = new_refresh_token
        await self.db.commit()

        logger.info("token_refreshed", user_id=str(user.id))

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=30 * 60,
        )

    async def logout(self, user: User) -> bool:
        """Logout user by invalidating refresh token.

        Args:
            user: Current user.

        Returns:
            True if successful.
        """
        user.refresh_token = None
        await self.db.commit()

        logger.info("user_logout", user_id=str(user.id))

        return True

    async def verify_email(self, token: str) -> Optional[User]:
        """Verify user email with token.

        Args:
            token: Verification token.

        Returns:
            Verified user or None if invalid.
        """
        result = await self.db.execute(
            select(User).where(
                User.verification_token == token,
                User.is_verified == False,
            )
        )
        user = result.scalar_one_or_none()

        if user is None:
            logger.warning("email_verification_failed", reason="invalid_token")
            return None

        user.is_verified = True
        user.verification_token = None
        user.verification_token_expires = None
        await self.db.commit()

        logger.info("email_verified", user_id=str(user.id))

        return user

    async def request_password_reset(self, email: str) -> Optional[str]:
        """Create password reset token.

        Args:
            email: User email.

        Returns:
            Reset token or None if user not found.
        """
        result = await self.db.execute(
            select(User).where(User.email == email, User.is_active == True)
        )
        user = result.scalar_one_or_none()

        if user is None:
            logger.warning("password_reset_request_failed", reason="user_not_found")
            return None

        # Generate reset token
        reset_token = generate_token()
        user.reset_token = reset_token
        user.reset_token_expires = datetime.now(timezone.utc)
        await self.db.commit()

        logger.info("password_reset_requested", user_id=str(user.id))

        return reset_token

    async def reset_password(self, token: str, new_password: str) -> Optional[User]:
        """Reset password with token.

        Args:
            token: Reset token.
            new_password: New password.

        Returns:
            User or None if invalid token.
        """
        result = await self.db.execute(
            select(User).where(User.reset_token == token)
        )
        user = result.scalar_one_or_none()

        if user is None:
            logger.warning("password_reset_failed", reason="invalid_token")
            return None

        user.hashed_password = get_password_hash(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        user.refresh_token = None  # Invalidate all sessions
        await self.db.commit()

        logger.info("password_reset_success", user_id=str(user.id))

        return user

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> bool:
        """Change user password.

        Args:
            user: Current user.
            current_password: Current password.
            new_password: New password.

        Returns:
            True if successful.
        """
        if not verify_password(current_password, user.hashed_password):
            logger.warning("password_change_failed", reason="invalid_current_password")
            return False

        user.hashed_password = get_password_hash(new_password)
        user.refresh_token = None  # Invalidate all sessions
        await self.db.commit()

        logger.info("password_changed", user_id=str(user.id))

        return True
