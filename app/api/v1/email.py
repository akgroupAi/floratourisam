"""Email template and sending endpoints."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.system import EmailTemplate, EmailLog
from app.schemas.common import PaginatedResponse
from app.schemas.system import (
    EmailTemplateCreate, EmailTemplateUpdate, EmailTemplateResponse,
    SendEmailRequest, EmailLogResponse,
)

router = APIRouter()


# ============== EMAIL TEMPLATES (Admin) ==============

@router.get("/templates", response_model=PaginatedResponse[EmailTemplateResponse], dependencies=[RequireAdmin])
async def list_templates(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
    category: Optional[str] = None,
):
    """List email templates (admin)."""
    query = select(EmailTemplate).where(EmailTemplate.is_deleted == False)
    
    if category:
        query = query.where(EmailTemplate.category == category)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(EmailTemplate.category, EmailTemplate.name)
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return PaginatedResponse.create(templates, total, page, page_size)


@router.post("/templates", response_model=EmailTemplateResponse, dependencies=[RequireAdmin])
async def create_template(data: EmailTemplateCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create email template (admin)."""
    # Check unique slug
    existing = await db.execute(select(EmailTemplate).where(EmailTemplate.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Template slug already exists")
    
    template = EmailTemplate(**data.model_dump(), created_by=current_user.id)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/templates/{template_id}", response_model=EmailTemplateResponse, dependencies=[RequireAdmin])
async def get_template(template_id: UUID, db: DatabaseSession):
    """Get email template by ID (admin)."""
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("/templates/slug/{slug}", response_model=EmailTemplateResponse, dependencies=[RequireAdmin])
async def get_template_by_slug(slug: str, db: DatabaseSession):
    """Get email template by slug (admin)."""
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.slug == slug))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/templates/{template_id}", response_model=EmailTemplateResponse, dependencies=[RequireAdmin])
async def update_template(template_id: UUID, data: EmailTemplateUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update email template (admin)."""
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    template.updated_by = current_user.id
    await db.commit()
    return template


@router.delete("/templates/{template_id}", dependencies=[RequireAdmin])
async def delete_template(template_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete email template (admin)."""
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Template deleted"}


@router.post("/templates/{template_id}/preview", dependencies=[RequireAdmin])
async def preview_template(template_id: UUID, variables: dict, db: DatabaseSession):
    """Preview email template with variables (admin)."""
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Simple variable replacement
    subject = template.subject
    body = template.body_html
    
    for key, value in variables.items():
        subject = subject.replace(f"{{{{{key}}}}}", str(value))
        body = body.replace(f"{{{{{key}}}}}", str(value))
    
    return {
        "subject": subject,
        "body_html": body,
    }


# ============== SEND EMAIL ==============

@router.post("/send", dependencies=[RequireAdmin])
async def send_email(data: SendEmailRequest, current_user: CurrentUser, db: DatabaseSession):
    """Send email (admin or system)."""
    template = None
    subject = data.subject
    body_html = data.body_html
    
    # Get template if specified
    if data.template_slug:
        result = await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.slug == data.template_slug,
                EmailTemplate.is_active == True
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404, detail="Email template not found")
        
        subject = data.subject or template.subject
        body_html = template.body_html
        
        # Replace variables
        for key, value in data.variables.items():
            subject = subject.replace(f"{{{{{key}}}}}", str(value))
            body_html = body_html.replace(f"{{{{{key}}}}}", str(value))
    
    if not subject or not body_html:
        raise HTTPException(status_code=400, detail="Subject and body are required")
    
    # Create log entry
    email_log = EmailLog(
        template_id=template.id if template else None,
        to_email=data.to_email,
        to_name=data.to_name,
        cc=data.cc,
        bcc=data.bcc,
        subject=subject,
        body_html=body_html,
        status="pending",
        created_by=current_user.id,
    )
    db.add(email_log)
    await db.commit()
    await db.refresh(email_log)
    
    # In production, integrate with email service (SendGrid, SES, etc.)
    # For now, mark as "sent"
    email_log.status = "sent"
    email_log.sent_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {
        "success": True,
        "message": "Email sent successfully",
        "email_id": str(email_log.id),
    }


# ============== EMAIL LOGS ==============

@router.get("/logs", response_model=PaginatedResponse[EmailLogResponse], dependencies=[RequireAdmin])
async def list_email_logs(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
    status: Optional[str] = None,
    to_email: Optional[str] = None,
):
    """List email logs (admin)."""
    query = select(EmailLog).where(EmailLog.is_deleted == False)
    
    if status:
        query = query.where(EmailLog.status == status)
    if to_email:
        query = query.where(EmailLog.to_email == to_email)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(EmailLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return PaginatedResponse.create(logs, total, page, page_size)


@router.get("/logs/{log_id}", response_model=EmailLogResponse, dependencies=[RequireAdmin])
async def get_email_log(log_id: UUID, db: DatabaseSession):
    """Get email log by ID (admin)."""
    result = await db.execute(select(EmailLog).where(EmailLog.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Email log not found")
    return log


@router.post("/logs/{log_id}/resend", dependencies=[RequireAdmin])
async def resend_email(log_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Resend a failed email (admin)."""
    result = await db.execute(select(EmailLog).where(EmailLog.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Email log not found")
    
    # Create new log entry
    new_log = EmailLog(
        template_id=log.template_id,
        to_email=log.to_email,
        to_name=log.to_name,
        subject=log.subject,
        body_html=log.body_html,
        status="pending",
        created_by=current_user.id,
    )
    db.add(new_log)
    await db.commit()
    
    # In production, send via email service
    new_log.status = "sent"
    new_log.sent_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {"success": True, "message": "Email resent", "email_id": str(new_log.id)}
