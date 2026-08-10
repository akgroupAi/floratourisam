"""Admin monitoring for the AI chatbot.

`ai_logs` records tokens, cost, and feedback for every exchange. Nothing read it in
aggregate before these endpoints.
"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DatabaseSession, RequireAdmin
from app.schemas.ai import (
    AdminAIConversationResponse,
    AdminAILogResponse,
    AdminAIStatsResponse,
    AIDailyUsage,
    AIKnowledgeStatusResponse,
    AITopQuestion,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services.ai_monitoring_service import AIMonitoringService

router = APIRouter()


@router.get(
    "/stats",
    response_model=AdminAIStatsResponse,
    dependencies=[RequireAdmin],
    summary="Chatbot usage and cost statistics",
)
async def get_ai_stats(
    db: DatabaseSession,
    from_date: Optional[date] = Query(None, description="Filter from this date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Filter to this date, inclusive"),
):
    """
    Spend, volume, and answer quality across all users.

    Watch `out_of_scope_rate` — a rising value means the scope gate is refusing real
    questions and `RAG_SCOPE_THRESHOLD` should come down.
    """
    return await AIMonitoringService(db).get_stats(from_date=from_date, to_date=to_date)


@router.get(
    "/usage/daily",
    response_model=List[AIDailyUsage],
    dependencies=[RequireAdmin],
    summary="Daily usage trend",
)
async def get_daily_usage(
    db: DatabaseSession,
    days: int = Query(30, ge=1, le=365, description="How many days back to report"),
):
    """Per-day messages, tokens, and cost — the series behind a spend chart."""
    return await AIMonitoringService(db).get_daily_usage(days=days)


@router.get(
    "/questions/top",
    response_model=List[AITopQuestion],
    dependencies=[RequireAdmin],
    summary="Most asked questions",
)
async def get_top_questions(
    db: DatabaseSession,
    limit: int = Query(20, ge=1, le=100),
    days: int = Query(30, ge=1, le=365),
):
    """What users actually ask. Useful for deciding which knowledge documents to write."""
    return await AIMonitoringService(db).get_top_questions(limit=limit, days=days)


@router.get(
    "/knowledge-status",
    response_model=AIKnowledgeStatusResponse,
    dependencies=[RequireAdmin],
    summary="Knowledge base contents and freshness",
)
async def get_knowledge_status(db: DatabaseSession):
    """
    What the chatbot currently has indexed, broken down by type, plus the active
    retrieval settings.

    The knowledge base is an in-memory snapshot per worker, so content added through
    the admin panel is not recommended until `POST /api/v1/ai/refresh-knowledge` runs.
    This endpoint reports the state of **the worker that served the request** — with
    several workers, the answer may differ between calls.
    """
    return await AIMonitoringService(db).get_knowledge_status()


@router.get(
    "/conversations",
    response_model=PaginatedResponse[AdminAIConversationResponse],
    dependencies=[RequireAdmin],
    summary="List all conversations",
)
async def list_conversations(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[UUID] = Query(None),
    context_type: Optional[str] = Query(None),
    rating: Optional[int] = Query(None, ge=1, le=5),
    search: Optional[str] = Query(None, description="Conversation title, user name or email"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    """Chatbot conversations across every user, newest first."""
    items, total = await AIMonitoringService(db).list_conversations(
        PaginationParams(page=page, page_size=page_size),
        user_id=user_id,
        context_type=context_type,
        rating=rating,
        search=search,
        from_date=from_date,
        to_date=to_date,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/logs",
    response_model=PaginatedResponse[AdminAILogResponse],
    dependencies=[RequireAdmin],
    summary="List individual chatbot exchanges",
)
async def list_logs(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conversation_id: Optional[UUID] = Query(None),
    user_id: Optional[UUID] = Query(None),
    is_helpful: Optional[bool] = Query(None, description="false surfaces thumbs-down answers"),
    is_error: Optional[bool] = Query(None),
    out_of_scope: Optional[bool] = Query(None, description="true shows refused off-topic questions"),
    search: Optional[str] = Query(None, description="Search the question or the answer"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    """Every question and answer, with retrieval counts and quality flags."""
    items, total = await AIMonitoringService(db).list_logs(
        PaginationParams(page=page, page_size=page_size),
        conversation_id=conversation_id,
        user_id=user_id,
        is_helpful=is_helpful,
        is_error=is_error,
        out_of_scope=out_of_scope,
        search=search,
        from_date=from_date,
        to_date=to_date,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/logs/flagged",
    response_model=PaginatedResponse[AdminAILogResponse],
    dependencies=[RequireAdmin],
    summary="Review queue — unhelpful and errored answers",
)
async def list_flagged_logs(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Answers users marked unhelpful, plus anything that errored.

    This is the queue to work through when improving the knowledge base — each entry
    is a question the chatbot handled badly.
    """
    service = AIMonitoringService(db)
    unhelpful, unhelpful_total = await service.list_logs(
        PaginationParams(page=page, page_size=page_size), is_helpful=False
    )
    errored, errored_total = await service.list_logs(
        PaginationParams(page=page, page_size=page_size), is_error=True
    )

    seen = {item["id"] for item in unhelpful}
    combined = unhelpful + [item for item in errored if item["id"] not in seen]
    combined.sort(key=lambda item: item["created_at"], reverse=True)
    return PaginatedResponse.create(
        combined[:page_size], unhelpful_total + errored_total, page, page_size
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=PaginatedResponse[AdminAILogResponse],
    dependencies=[RequireAdmin],
    summary="Full transcript of one conversation",
)
async def get_conversation_transcript(
    conversation_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
):
    """Every exchange in one conversation, for any user."""
    items, total = await AIMonitoringService(db).list_logs(
        PaginationParams(page=page, page_size=page_size),
        conversation_id=conversation_id,
    )
    if not items and page == 1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or has no messages",
        )
    return PaginatedResponse.create(items, total, page, page_size)
