"""Public contact form endpoints."""

from fastapi import APIRouter, status

from app.api.deps import DatabaseSession
from app.schemas.contact import ContactCreate, ContactSubmitResponse
from app.services.contact_service import ContactService

router = APIRouter()


@router.post(
    "",
    response_model=ContactSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit contact form",
    description=(
        "Submit the Contact Us form. Sends an email notification to the admin "
        "and stores the inquiry for follow-up."
    ),
)
async def submit_contact_form(data: ContactCreate, db: DatabaseSession):
    """Submit a contact form from the public website."""
    service = ContactService(db)
    lead = await service.submit(data)
    return ContactSubmitResponse(
        message="Thank you for contacting us. We'll respond within 24 hours.",
        reference_id=lead.id,
    )
