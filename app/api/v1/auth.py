"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import (
    AuthResponse, ChangePasswordRequest, LoginRequest,
    PasswordResetConfirm, PasswordResetRequest, RefreshTokenRequest,
    RegisterRequest, TokenResponse, VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService
from app.utils.email_sender import send_email

router = APIRouter()


def _build_verification_email_html(full_name: str, token: str) -> str:
    """Render a simple HTML verification email."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;
                  overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <div style="background:#0066cc;padding:24px;text-align:center;">
          <h1 style="color:#fff;margin:0;font-size:22px;">Verify Your Email</h1>
        </div>
        <div style="padding:32px;">
          <p style="font-size:16px;color:#333;">Dear <strong>{full_name}</strong>,</p>
          <p style="font-size:14px;color:#555;">
            Thank you for registering. Please use the verification code below to
            activate your account:
          </p>
          <div style="background:#f0f4ff;border-radius:6px;padding:16px 24px;
                      text-align:center;margin:24px 0;">
            <code style="font-size:20px;letter-spacing:4px;color:#0066cc;
                         font-weight:bold;">{token}</code>
          </div>
          <p style="font-size:13px;color:#888;">
            If you did not create an account, you can safely ignore this email.
          </p>
        </div>
        <div style="background:#f9f9f9;padding:16px;text-align:center;">
          <p style="font-size:12px;color:#aaa;margin:0;">{settings.EMAIL_FROM_NAME}</p>
        </div>
      </div>
    </body>
    </html>
    """


def _build_reset_email_html(full_name: str, token: str) -> str:
    """Render a simple HTML password-reset email."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;
                  overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <div style="background:#cc3300;padding:24px;text-align:center;">
          <h1 style="color:#fff;margin:0;font-size:22px;">Password Reset Request</h1>
        </div>
        <div style="padding:32px;">
          <p style="font-size:16px;color:#333;">Dear <strong>{full_name}</strong>,</p>
          <p style="font-size:14px;color:#555;">
            Use the token below to reset your password:
          </p>
          <div style="background:#fff0f0;border-radius:6px;padding:16px 24px;
                      text-align:center;margin:24px 0;">
            <code style="font-size:20px;letter-spacing:4px;color:#cc3300;
                         font-weight:bold;">{token}</code>
          </div>
          <p style="font-size:13px;color:#888;">
            If you did not request a password reset, please ignore this email.
          </p>
        </div>
        <div style="background:#f9f9f9;padding:16px;text-align:center;">
          <p style="font-size:12px;color:#aaa;margin:0;">{settings.EMAIL_FROM_NAME}</p>
        </div>
      </div>
    </body>
    </html>
    """


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: DatabaseSession):
    """Authenticate user and return tokens."""
    service = AuthService(db)
    result = await service.login(request)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return result


@router.post("/register", response_model=MessageResponse)
async def register(request: RegisterRequest, db: DatabaseSession):
    """Register a new user."""
    service = AuthService(db)
    user = await service.register(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
<<<<<<< HEAD
    return MessageResponse(message="Registration successful. We have sent a verification link to your email.")
=======

    # Send verification email (best-effort — don't fail registration if email fails)
    if user.verification_token:
        await send_email(
            db=db,
            to_email=user.email,
            to_name=user.full_name,
            subject="Verify your email address",
            body_html=_build_verification_email_html(user.full_name, user.verification_token),
            category="verification",
            user_id=user.id,
        )

    return MessageResponse(message="Registration successful. Please check your email to verify your account.")
>>>>>>> 26cae43 (Fix: Email authentication)


@router.post("/admin/register", response_model=MessageResponse, dependencies=[RequireAdmin])
async def register_admin(request: RegisterRequest, current_user: CurrentUser, db: DatabaseSession):
    """Register a new admin user (requires admin authentication)."""
    # Validate role is admin or super_admin
    from app.utils.enums import UserRole
    
    if request.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only for creating admin users"
        )
    
    # Check if email already exists
    existing_result = await db.execute(
        select(User).where(User.email == request.email)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    service = AuthService(db)
    user = await service.register(request)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create admin user"
        )
    
    return MessageResponse(message=f"Admin user created successfully: {user.email}")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: DatabaseSession):
    """Refresh access token."""
    service = AuthService(db)
    result = await service.refresh_tokens(request.refresh_token)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return result


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: CurrentUser, db: DatabaseSession):
    """Logout current user."""
    service = AuthService(db)
    await service.logout(current_user)
    return MessageResponse(message="Logged out successfully")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(request: VerifyEmailRequest, db: DatabaseSession):
    """Verify user email."""
    service = AuthService(db)
    user = await service.verify_email(request.token)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
    return MessageResponse(message="Email verified successfully")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(request: PasswordResetRequest, db: DatabaseSession):
    """Request password reset."""
    service = AuthService(db)
    reset_token = await service.request_password_reset(request.email)

    # If a token was generated, look up the user and send the reset email
    if reset_token:
        from sqlalchemy import select as _select
        result = await db.execute(
            _select(User).where(User.email == request.email)
        )
        user = result.scalar_one_or_none()
        if user:
            await send_email(
                db=db,
                to_email=user.email,
                to_name=user.full_name,
                subject="Password reset request",
                body_html=_build_reset_email_html(user.full_name, reset_token),
                category="password_reset",
                user_id=user.id,
            )

    return MessageResponse(message="If email exists, reset instructions have been sent")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(request: PasswordResetConfirm, db: DatabaseSession):
    """Reset password with token."""
    service = AuthService(db)
    user = await service.reset_password(request.token, request.new_password)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
    return MessageResponse(message="Password reset successfully")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(request: ChangePasswordRequest, current_user: CurrentUser, db: DatabaseSession):
    """Change current user's password."""
    service = AuthService(db)
    success = await service.change_password(current_user, request.current_password, request.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid current password")
    return MessageResponse(message="Password changed successfully")
