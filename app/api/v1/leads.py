"""Lead submission endpoints."""

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DatabaseSession, OptionalUser
from app.models.site import LeadSubmission
from app.schemas.site import LeadSubmissionCreate, ContactSubmission

router = APIRouter()


@router.post("/quote")
async def submit_quote_request(data: LeadSubmissionCreate, db: DatabaseSession):
    """Submit a quote request (public)."""
    lead = LeadSubmission(**data.model_dump())
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    
    return {
        "success": True,
        "message": "Thank you! We've received your request and will contact you within 24 hours.",
        "reference_id": str(lead.id),
    }


@router.post("/contact")
async def submit_contact_form(data: ContactSubmission, db: DatabaseSession):
    """Submit contact form (public) and notify admin."""
    from app.utils.email_sender import send_email, render_contact_lead_email_html
    from app.core.config import settings

    # 1. Save to DB
    lead = LeadSubmission(
        email=data.email,
        name=data.name,
        phone=data.phone,
        country=data.country,
        treatment_interest=data.treatment_interest or data.subject,
        message=data.message,
        form_source="contact_page",
    )
    db.add(lead)
    await db.flush() # Flush to get ID if needed
    
    # 2. Notify Admin via Email
    await send_email(
        db=db,
        to_email=settings.FIRST_SUPERUSER_EMAIL,
        to_name="Admin",
        subject=f"New Contact Lead: {data.name}",
        body_html=render_contact_lead_email_html(
            name=data.name,
            email=data.email,
            phone=data.phone,
            country=data.country,
            treatment=data.treatment_interest or data.subject,
            message=data.message
        ),
        category="lead_notification"
    )
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Thank you for contacting us. We'll respond within 24 hours.",
    }


@router.post("/newsletter")
async def subscribe_newsletter(email: str, db: DatabaseSession):
    """Subscribe to newsletter (public)."""
    # In production, integrate with email service like Mailchimp
    return {
        "success": True,
        "message": "You've been subscribed to our newsletter!",
    }


@router.post("/callback")
async def request_callback(phone: str, name: str = None, db: DatabaseSession = None):
    """Request a callback (public)."""
    lead = LeadSubmission(
        phone=phone,
        name=name,
        form_source="callback_request",
    )
    db.add(lead)
    await db.commit()
    
    return {
        "success": True,
        "message": "We'll call you back shortly!",
    }
