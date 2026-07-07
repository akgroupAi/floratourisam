"""Lead submission endpoints."""

from fastapi import APIRouter

from app.api.deps import DatabaseSession
from app.models.site import LeadSubmission
from app.schemas.contact import ContactCreate, ContactSubmitResponse
from app.schemas.site import LeadSubmissionCreate
from app.services.contact_service import ContactService

router = APIRouter()


@router.post("/quote")
async def submit_quote_request(data: LeadSubmissionCreate, db: DatabaseSession):
    """Submit a quote request (public)."""
    payload = data.model_dump()
    # Tag the source so admin can list quote submissions reliably.
    if not payload.get("form_source"):
        payload["form_source"] = "quote_form"
    lead = LeadSubmission(**payload)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    
    return {
        "success": True,
        "message": "Thank you! We've received your request and will contact you within 24 hours.",
        "reference_id": str(lead.id),
    }


@router.post("/contact", response_model=ContactSubmitResponse, deprecated=True)
async def submit_contact_form_legacy(data: ContactCreate, db: DatabaseSession):
    """Submit contact form (legacy path — prefer POST /api/v1/contact)."""
    service = ContactService(db)
    lead = await service.submit(data)
    return ContactSubmitResponse(
        message="Thank you for contacting us. We'll respond within 24 hours.",
        reference_id=lead.id,
    )


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
