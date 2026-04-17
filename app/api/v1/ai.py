"""AI chat endpoints — RAG-based chatbot with OpenAI."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.ai_log import AIConversation, AILog
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    AIConversationDetailResponse,
    AIConversationResponse,
    AIFeedbackRequest,
    AIReportAnalysisRequest,
    AIReportAnalysisResponse,
    DoctorSuggestion,
    RecommendedDoctor,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.rag_service import RAGChatService, rebuild_knowledge_base

router = APIRouter()


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    request: AIChatRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Send a message to the AI medical assistant.

    The assistant uses RAG to find relevant doctors, hospitals, and treatments,
    then responds with context-aware medical tourism guidance.
    """
    try:
        service = RAGChatService(db)
        result = await service.chat(
            user_id=current_user.id,
            message=request.message,
            session_id=request.session_id,
            context_type=request.context_type,
            context_data=request.context_data,
            report_text=request.report_text,
        )
        return AIChatResponse(
            response=result["response"],
            session_id=result["session_id"],
            conversation_id=result["conversation_id"],
            doctor_suggestions=[
                DoctorSuggestion(**d) for d in result["doctor_suggestions"]
            ],
            follow_up_questions=result["follow_up_questions"],
            tokens_used=result["tokens_used"],
            response_time_ms=result["response_time_ms"],
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")


@router.post("/analyze-report", response_model=AIReportAnalysisResponse)
async def analyze_report(
    request: AIReportAnalysisRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Upload/paste a medical report for analysis and doctor recommendations.

    The AI extracts conditions from the report and matches with relevant
    doctors on the platform. Returns structured analysis + doctor suggestions
    with profile links.
    """
    try:
        service = RAGChatService(db)
        result = await service.parse_report_and_suggest(
            user_id=current_user.id,
            report_text=request.report_text,
            session_id=request.session_id,
        )
        return AIReportAnalysisResponse(
            report_analysis=result["report_analysis"],
            recommended_doctors=[
                RecommendedDoctor(**d) for d in result["recommended_doctors"]
            ],
            total_matches=result["total_matches"],
            response_time_ms=result["response_time_ms"],
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")


@router.get("/conversations", response_model=PaginatedResponse[AIConversationResponse])
async def list_conversations(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
):
    """List the current user's AI conversations."""
    offset = (page - 1) * page_size

    base_filter = [
        AIConversation.user_id == current_user.id,
        AIConversation.is_deleted == False,
    ]
    if search:
        base_filter.append(AIConversation.title.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(AIConversation).where(*base_filter)
    total = (await db.execute(count_q)).scalar() or 0

    rows_q = (
        select(AIConversation)
        .where(*base_filter)
        .order_by(AIConversation.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(rows_q)).scalars().all()

    return PaginatedResponse.create(rows, total, page, page_size)


@router.get("/conversations/{conversation_id}", response_model=AIConversationDetailResponse)
async def get_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Get a conversation with its message history."""
    result = await db.execute(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    logs_result = await db.execute(
        select(AILog)
        .where(AILog.conversation_id == conversation_id)
        .order_by(AILog.created_at.asc())
    )
    messages = logs_result.scalars().all()

    return AIConversationDetailResponse(
        **{
            "id": conv.id,
            "session_id": conv.session_id,
            "title": conv.title,
            "context_type": conv.context_type,
            "is_active": conv.is_active,
            "message_count": conv.message_count or 0,
            "total_tokens_used": conv.total_tokens_used or 0,
            "estimated_cost": conv.estimated_cost or 0.0,
            "rating": conv.rating,
            "feedback": conv.feedback,
            "created_at": conv.created_at,
            "ended_at": conv.ended_at,
            "messages": messages,
        }
    )


@router.post("/feedback", response_model=MessageResponse)
async def submit_feedback(
    data: AIFeedbackRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Submit feedback for an AI response."""
    result = await db.execute(
        select(AILog).where(AILog.id == data.log_id, AILog.user_id == current_user.id)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="AI log not found")

    log.is_helpful = data.is_helpful
    log.feedback = data.feedback
    await db.commit()
    return MessageResponse(message="Feedback submitted successfully")


@router.patch("/conversations/{conversation_id}", response_model=AIConversationResponse)
async def rename_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    title: str = Query(..., max_length=255),
):
    """Rename an AI conversation."""
    result = await db.execute(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == current_user.id,
            AIConversation.is_deleted == False,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.title = title
    await db.commit()
    await db.refresh(conv)
    return conv


@router.delete("/conversations/{conversation_id}", response_model=MessageResponse)
async def delete_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Delete (soft) an AI conversation."""
    result = await db.execute(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == current_user.id,
            AIConversation.is_deleted == False,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.is_deleted = True
    conv.deleted_at = datetime.now(timezone.utc)
    conv.is_active = False
    await db.commit()
    return MessageResponse(message="Conversation deleted")


@router.delete("/conversations", response_model=MessageResponse)
async def clear_all_conversations(
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Clear (soft-delete) all conversations for the current user."""
    await db.execute(
        update(AIConversation)
        .where(
            AIConversation.user_id == current_user.id,
            AIConversation.is_deleted == False,
        )
        .values(
            is_deleted=True,
            deleted_at=datetime.now(timezone.utc),
            is_active=False,
        )
    )
    await db.commit()
    return MessageResponse(message="All conversations cleared")


@router.post("/refresh-knowledge", response_model=MessageResponse, dependencies=[RequireAdmin])
async def refresh_knowledge_base(db: DatabaseSession):
    """Admin-only: rebuild the AI knowledge base from current database data."""
    count = await rebuild_knowledge_base(db)
    return MessageResponse(message=f"Knowledge base rebuilt with {count} documents")
