"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DatabaseSession
from app.schemas.auth import (
    AuthResponse, ChangePasswordRequest, LoginRequest,
    PasswordResetConfirm, PasswordResetRequest, RefreshTokenRequest,
    RegisterRequest, TokenResponse, VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService

router = APIRouter()


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
    return MessageResponse(message="Registration successful. Please verify your email.")


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
    await service.request_password_reset(request.email)
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
