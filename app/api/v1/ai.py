"""AI chat endpoints."""

from uuid import UUID
from fastapi import APIRouter, Query
from app.api.deps import CurrentUser, DatabaseSession
from app.schemas.ai import AIChatRequest, AIChatResponse, AIConversationResponse, AIFeedbackRequest
from app.schemas.common import PaginatedResponse
from app.services.ai_service import AIService

router = APIRouter()


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(request: AIChatRequest, current_user: CurrentUser, db: DatabaseSession):
    """Send message to AI assistant."""
    service = AIService(db)
    
    # Create or get conversation
    if not request.session_id:
        conv = await service.create_conversation(current_user.id, request.context_type)
        session_id = conv.session_id
    else:
        session_id = request.session_id
    
    # Mock AI response (integrate with actual AI service)
    ai_response = "I'm the medical tourism assistant. How can I help you today?"
    
    return AIChatResponse(
        response=ai_response,
        session_id=session_id,
        intent="greeting",
        confidence=0.95,
        suggestions=["Book a consultation", "Find a hospital", "View my bookings"],
    )


@router.get("/conversations", response_model=PaginatedResponse[AIConversationResponse])
async def list_conversations(current_user: CurrentUser, db: DatabaseSession, page: int = Query(1), page_size: int = Query(20)):
    """List user's AI conversations."""
    return PaginatedResponse.create([], 0, page, page_size)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Get conversation with messages."""
    return {"id": conversation_id, "messages": []}


@router.post("/feedback")
async def submit_feedback(data: AIFeedbackRequest, current_user: CurrentUser, db: DatabaseSession):
    """Submit feedback for AI response."""
    return {"message": "Feedback submitted"}
