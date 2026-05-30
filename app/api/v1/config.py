"""Admin configuration endpoints."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin, RequireSuperAdmin
from app.models.system import AdminConfig
from app.schemas.common import PaginatedResponse
from app.schemas.system import (
    AdminConfigCreate, AdminConfigUpdate, AdminConfigResponse,
    AdminConfigPublicResponse, ConfigBulkUpdate,
)

router = APIRouter()


# ============== PUBLIC CONFIGS ==============

@router.get("/public")
async def get_public_configs(db: DatabaseSession):
    """Get public configuration values."""
    result = await db.execute(
        select(AdminConfig).where(
            AdminConfig.is_public == True,
            AdminConfig.is_active == True,
            AdminConfig.is_deleted == False,
        )
    )
    configs = result.scalars().all()
    
    return {
        config.key: config.value if not config.is_sensitive else "***"
        for config in configs
    }


# ============== ADMIN CONFIG MANAGEMENT ==============

@router.get("", response_model=List[AdminConfigResponse], dependencies=[RequireAdmin])
async def list_configs(
    db: DatabaseSession,
    category: Optional[str] = None,
):
    """List all configurations (admin)."""
    query = select(AdminConfig).where(AdminConfig.is_deleted == False)
    
    if category:
        query = query.where(AdminConfig.category == category)
    
    result = await db.execute(query.order_by(AdminConfig.category, AdminConfig.key))
    configs = result.scalars().all()
    
    return configs


@router.get("/categories", dependencies=[RequireAdmin])
async def get_config_categories(db: DatabaseSession):
    """Get config categories."""
    result = await db.execute(
        select(AdminConfig.category, func.count(AdminConfig.id))
        .where(AdminConfig.is_deleted == False)
        .group_by(AdminConfig.category)
    )
    return [{"name": cat, "count": count} for cat, count in result.all()]


@router.post("", response_model=AdminConfigResponse, dependencies=[RequireSuperAdmin])
async def create_config(data: AdminConfigCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create configuration (super admin)."""
    # Check unique key
    existing = await db.execute(select(AdminConfig).where(AdminConfig.key == data.key))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Config key already exists")
    
    config = AdminConfig(
        **data.model_dump(),
        created_by=current_user.id,
        last_modified_by=current_user.id,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.get("/{key}", response_model=AdminConfigResponse, dependencies=[RequireAdmin])
async def get_config(key: str, db: DatabaseSession):
    """Get configuration by key (admin)."""
    result = await db.execute(select(AdminConfig).where(AdminConfig.key == key))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config


@router.put("/{key}", response_model=AdminConfigResponse, dependencies=[RequireAdmin])
async def update_config(key: str, data: AdminConfigUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update configuration value (admin)."""
    result = await db.execute(select(AdminConfig).where(AdminConfig.key == key))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    config.value = data.value
    if data.description:
        config.description = data.description
    config.last_modified_by = current_user.id
    config.updated_by = current_user.id
    await db.commit()
    return config


@router.post("/bulk-update", dependencies=[RequireAdmin])
async def bulk_update_configs(data: ConfigBulkUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Bulk update configuration values (admin)."""
    updated = []
    errors = []
    
    for key, value in data.configs.items():
        result = await db.execute(select(AdminConfig).where(AdminConfig.key == key))
        config = result.scalar_one_or_none()
        
        if config:
            config.value = {"value": value} if not isinstance(value, dict) else value
            config.last_modified_by = current_user.id
            updated.append(key)
        else:
            errors.append({"key": key, "error": "Config not found"})
    
    await db.commit()
    
    return {
        "updated": updated,
        "errors": errors,
        "message": f"Updated {len(updated)} configurations",
    }


@router.delete("/{key}", dependencies=[RequireSuperAdmin])
async def delete_config(key: str, current_user: CurrentUser, db: DatabaseSession):
    """Delete configuration (super admin)."""
    result = await db.execute(select(AdminConfig).where(AdminConfig.key == key))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    config.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Config deleted"}


# ============== CONFIG CATEGORIES ==============

@router.get("/by-category/{category}", response_model=List[AdminConfigResponse], dependencies=[RequireAdmin])
async def get_configs_by_category(category: str, db: DatabaseSession):
    """Get all configs in a category (admin)."""
    result = await db.execute(
        select(AdminConfig)
        .where(AdminConfig.category == category, AdminConfig.is_deleted == False)
        .order_by(AdminConfig.key)
    )
    return result.scalars().all()


# ============== DEFAULT CONFIGS ==============

@router.post("/init-defaults", dependencies=[RequireSuperAdmin])
async def init_default_configs(current_user: CurrentUser, db: DatabaseSession):
    """Initialize default configurations (super admin)."""
    
    defaults = [
        # General
        {"key": "SITE_NAME", "value": {"value": "Flora Medical"}, "category": "general", "name": "Site Name", "is_public": True},
        {"key": "SITE_TAGLINE", "value": {"value": "AI-Powered Medical Tourism"}, "category": "general", "name": "Site Tagline", "is_public": True},
        {"key": "DEFAULT_CURRENCY", "value": {"value": "USD"}, "category": "general", "name": "Default Currency", "is_public": True},
        {"key": "DEFAULT_TIMEZONE", "value": {"value": "UTC"}, "category": "general", "name": "Default Timezone", "is_public": True},
        
        # Email
        {"key": "SMTP_HOST", "value": {"value": ""}, "category": "email", "name": "SMTP Host", "is_sensitive": True},
        {"key": "SMTP_PORT", "value": {"value": 587}, "category": "email", "name": "SMTP Port", "value_type": "number"},
        {"key": "SMTP_USERNAME", "value": {"value": ""}, "category": "email", "name": "SMTP Username", "is_sensitive": True},
        {"key": "SMTP_PASSWORD", "value": {"value": ""}, "category": "email", "name": "SMTP Password", "is_sensitive": True},
        {"key": "FROM_EMAIL", "value": {"value": "noreply@floramedical.com"}, "category": "email", "name": "From Email"},
        {"key": "FROM_NAME", "value": {"value": "Flora Medical"}, "category": "email", "name": "From Name"},
        
        # Payment (Razorpay Only)
        {"key": "PAYMENT_CURRENCY", "value": {"value": "INR"}, "category": "payment", "name": "Payment Currency", "is_public": True},
        
        # Booking
        {"key": "BOOKING_ADVANCE_DAYS", "value": {"value": 30}, "category": "booking", "name": "Max Advance Booking Days", "value_type": "number"},
        {"key": "CANCELLATION_HOURS", "value": {"value": 24}, "category": "booking", "name": "Cancellation Window (hours)", "value_type": "number"},
        {"key": "REFUND_PERCENTAGE", "value": {"value": 80}, "category": "booking", "name": "Refund Percentage", "value_type": "number"},
        
        # Notification
        {"key": "ENABLE_EMAIL_NOTIFICATIONS", "value": {"value": True}, "category": "notification", "name": "Enable Email Notifications", "value_type": "boolean"},
        {"key": "ENABLE_PUSH_NOTIFICATIONS", "value": {"value": True}, "category": "notification", "name": "Enable Push Notifications", "value_type": "boolean"},
        {"key": "ENABLE_SMS_NOTIFICATIONS", "value": {"value": False}, "category": "notification", "name": "Enable SMS Notifications", "value_type": "boolean"},
        
        # SEO
        {"key": "META_TITLE", "value": {"value": "Flora Medical - AI-Powered Medical Tourism"}, "category": "seo", "name": "Default Meta Title", "is_public": True},
        {"key": "META_DESCRIPTION", "value": {"value": "World-class medical care at affordable prices"}, "category": "seo", "name": "Default Meta Description", "is_public": True},
        {"key": "GOOGLE_ANALYTICS_ID", "value": {"value": ""}, "category": "seo", "name": "Google Analytics ID", "is_public": True},
        
        # Integration
        {"key": "OPENAI_API_KEY", "value": {"value": ""}, "category": "integration", "name": "OpenAI API Key", "is_sensitive": True},
        {"key": "TWILIO_SID", "value": {"value": ""}, "category": "integration", "name": "Twilio Account SID", "is_sensitive": True},
        {"key": "TWILIO_AUTH_TOKEN", "value": {"value": ""}, "category": "integration", "name": "Twilio Auth Token", "is_sensitive": True},
    ]
    
    created = 0
    for config_data in defaults:
        existing = await db.execute(select(AdminConfig).where(AdminConfig.key == config_data["key"]))
        if not existing.scalar_one_or_none():
            config = AdminConfig(
                **config_data,
                value_type=config_data.get("value_type", "string"),
                is_public=config_data.get("is_public", False),
                is_sensitive=config_data.get("is_sensitive", False),
                created_by=current_user.id,
                last_modified_by=current_user.id,
            )
            db.add(config)
            created += 1
    
    await db.commit()
    return {"message": f"Created {created} default configurations"}
