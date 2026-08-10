"""Admin monitoring for the AI chatbot — spend, quality, and knowledge freshness."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import Float, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.ai_log import AIConversation, AILog
from app.models.user import User
from app.schemas.common import PaginationParams

logger = get_logger(__name__)


class AIMonitoringService:
    """Aggregates ai_logs and ai_conversations for the admin panel."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _date_filters(column, from_date, to_date) -> list:
        filters = []
        if from_date:
            filters.append(
                column >= datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
            )
        if to_date:
            filters.append(
                column
                < datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)
                + timedelta(days=1)
            )
        return filters

    async def get_stats(self, from_date=None, to_date=None) -> dict:
        """Usage, spend, and answer quality over the given window."""
        log_filters = [AILog.is_deleted == False] + self._date_filters(
            AILog.created_at, from_date, to_date
        )
        conv_filters = [AIConversation.is_deleted == False] + self._date_filters(
            AIConversation.created_at, from_date, to_date
        )

        totals = (
            await self.db.execute(
                select(
                    func.count(AILog.id),
                    func.coalesce(func.sum(AILog.total_tokens), 0),
                    func.coalesce(func.sum(AILog.cost), 0.0),
                    func.coalesce(func.avg(AILog.response_time_ms), 0.0),
                ).where(*log_filters)
            )
        ).one()
        total_messages, total_tokens, total_cost, avg_response_ms = totals

        total_conversations = (
            await self.db.execute(
                select(func.count(AIConversation.id)).where(*conv_filters)
            )
        ).scalar() or 0

        errors = (
            await self.db.execute(
                select(func.count(AILog.id)).where(*log_filters, AILog.is_error == True)
            )
        ).scalar() or 0

        helpful = (
            await self.db.execute(
                select(func.count(AILog.id)).where(*log_filters, AILog.is_helpful == True)
            )
        ).scalar() or 0
        unhelpful = (
            await self.db.execute(
                select(func.count(AILog.id)).where(*log_filters, AILog.is_helpful == False)
            )
        ).scalar() or 0

        avg_rating = (
            await self.db.execute(
                select(func.avg(AIConversation.rating)).where(
                    *conv_filters, AIConversation.rating.isnot(None)
                )
            )
        ).scalar()

        intents = dict(
            (
                await self.db.execute(
                    select(AILog.detected_intent, func.count(AILog.id))
                    .where(*log_filters, AILog.detected_intent.isnot(None))
                    .group_by(AILog.detected_intent)
                )
            ).all()
        )
        by_context = dict(
            (
                await self.db.execute(
                    select(AIConversation.context_type, func.count(AIConversation.id))
                    .where(*conv_filters)
                    .group_by(AIConversation.context_type)
                )
            ).all()
        )
        by_model = dict(
            (
                await self.db.execute(
                    select(AILog.model_name, func.count(AILog.id))
                    .where(*log_filters)
                    .group_by(AILog.model_name)
                )
            ).all()
        )

        # in_scope is written into request_metadata by the RAG service. Older rows
        # predate it, so absence is counted as in-scope rather than as a refusal.
        out_of_scope = (
            await self.db.execute(
                select(func.count(AILog.id)).where(
                    *log_filters,
                    AILog.request_metadata["in_scope"].astext == "false",
                )
            )
        ).scalar() or 0

        rated = helpful + unhelpful
        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages or 0,
            "total_tokens_used": int(total_tokens or 0),
            "total_cost": round(float(total_cost or 0), 4),
            "average_response_time_ms": round(float(avg_response_ms or 0), 1),
            "average_rating": round(float(avg_rating), 2) if avg_rating is not None else None,
            "error_count": errors,
            "error_rate": round(errors / total_messages * 100, 2) if total_messages else 0.0,
            "helpful_count": helpful,
            "unhelpful_count": unhelpful,
            "satisfaction_rate": round(helpful / rated * 100, 2) if rated else None,
            "out_of_scope_count": out_of_scope,
            "out_of_scope_rate": round(out_of_scope / total_messages * 100, 2) if total_messages else 0.0,
            "cost_per_conversation": round(float(total_cost or 0) / total_conversations, 4)
            if total_conversations
            else 0.0,
            "intents_distribution": intents,
            "conversations_by_context": by_context,
            "messages_by_model": by_model,
        }

    async def get_daily_usage(self, days: int = 30) -> List[dict]:
        """Per-day message count, token spend, and cost for a trend chart."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        day = func.date_trunc("day", AILog.created_at).label("day")
        rows = (
            await self.db.execute(
                select(
                    day,
                    func.count(AILog.id),
                    func.coalesce(func.sum(AILog.total_tokens), 0),
                    func.coalesce(func.sum(AILog.cost), 0.0),
                )
                .where(AILog.is_deleted == False, AILog.created_at >= since)
                .group_by(day)
                .order_by(day)
            )
        ).all()
        return [
            {
                "date": d.date().isoformat() if hasattr(d, "date") else str(d),
                "messages": count,
                "tokens": int(tokens or 0),
                "cost": round(float(cost or 0), 4),
            }
            for d, count, tokens, cost in rows
        ]

    async def list_conversations(
        self,
        pagination: PaginationParams,
        user_id: Optional[UUID] = None,
        context_type: Optional[str] = None,
        rating: Optional[int] = None,
        search: Optional[str] = None,
        from_date=None,
        to_date=None,
    ) -> Tuple[List[dict], int]:
        """Conversations across all users, with the owner attached."""
        filters = [AIConversation.is_deleted == False] + self._date_filters(
            AIConversation.created_at, from_date, to_date
        )
        if user_id:
            filters.append(AIConversation.user_id == user_id)
        if context_type:
            filters.append(AIConversation.context_type == context_type)
        if rating is not None:
            filters.append(AIConversation.rating == rating)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    AIConversation.title.ilike(like),
                    User.full_name.ilike(like),
                    User.email.ilike(like),
                )
            )

        base = (
            select(AIConversation, User.full_name, User.email)
            .outerjoin(User, AIConversation.user_id == User.id)
            .where(*filters)
        )
        total = (
            await self.db.execute(
                select(func.count())
                .select_from(AIConversation)
                .outerjoin(User, AIConversation.user_id == User.id)
                .where(*filters)
            )
        ).scalar() or 0

        rows = (
            await self.db.execute(
                base.order_by(AIConversation.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).all()

        return [
            {
                "id": conv.id,
                "user_id": conv.user_id,
                "user_name": name,
                "user_email": email,
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
            }
            for conv, name, email in rows
        ], total

    async def list_logs(
        self,
        pagination: PaginationParams,
        conversation_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        is_helpful: Optional[bool] = None,
        is_error: Optional[bool] = None,
        out_of_scope: Optional[bool] = None,
        search: Optional[str] = None,
        from_date=None,
        to_date=None,
    ) -> Tuple[List[dict], int]:
        """Individual messages across all users — the review queue."""
        filters = [AILog.is_deleted == False] + self._date_filters(
            AILog.created_at, from_date, to_date
        )
        if conversation_id:
            filters.append(AILog.conversation_id == conversation_id)
        if user_id:
            filters.append(AILog.user_id == user_id)
        if is_helpful is not None:
            filters.append(AILog.is_helpful == is_helpful)
        if is_error is not None:
            filters.append(AILog.is_error == is_error)
        if out_of_scope is True:
            filters.append(AILog.request_metadata["in_scope"].astext == "false")
        elif out_of_scope is False:
            filters.append(
                or_(
                    AILog.request_metadata["in_scope"].astext == "true",
                    AILog.request_metadata["in_scope"].astext.is_(None),
                )
            )
        if search:
            like = f"%{search}%"
            filters.append(
                or_(AILog.user_message.ilike(like), AILog.ai_response.ilike(like))
            )

        total = (
            await self.db.execute(
                select(func.count()).select_from(
                    select(AILog.id).where(*filters).subquery()
                )
            )
        ).scalar() or 0

        rows = (
            await self.db.execute(
                select(AILog, User.full_name, User.email)
                .outerjoin(User, AILog.user_id == User.id)
                .where(*filters)
                .order_by(AILog.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).all()

        return [
            {
                "id": log.id,
                "conversation_id": log.conversation_id,
                "user_id": log.user_id,
                "user_name": name,
                "user_email": email,
                "user_message": log.user_message,
                "ai_response": log.ai_response,
                "model_name": log.model_name,
                "total_tokens": log.total_tokens,
                "cost": log.cost,
                "response_time_ms": log.response_time_ms,
                "is_error": log.is_error,
                "error_message": log.error_message,
                "is_helpful": log.is_helpful,
                "feedback": log.feedback,
                "in_scope": (log.request_metadata or {}).get("in_scope", True),
                "retrieved_doc_count": (log.request_metadata or {}).get("relevant_docs_count", 0),
                "retrieved_doc_types": (log.request_metadata or {}).get("doc_types", []),
                "created_at": log.created_at,
            }
            for log, name, email in rows
        ], total

    async def get_top_questions(self, limit: int = 20, days: int = 30) -> List[dict]:
        """Most frequently asked questions, normalised to lowercase."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        normalised = func.lower(func.trim(AILog.user_message)).label("question")
        rows = (
            await self.db.execute(
                select(normalised, func.count(AILog.id).label("count"))
                .where(AILog.is_deleted == False, AILog.created_at >= since)
                .group_by(normalised)
                .order_by(func.count(AILog.id).desc())
                .limit(limit)
            )
        ).all()
        return [{"question": q, "count": c} for q, c in rows]

    async def get_knowledge_status(self) -> dict:
        """What the chatbot currently knows, and whether that snapshot is stale."""
        from app.services.rag_service import _knowledge_base

        by_type: dict[str, int] = {}
        for doc in _knowledge_base.documents:
            doc_type = doc.get("type", "unknown")
            by_type[doc_type] = by_type.get(doc_type, 0) + 1

        return {
            "is_built": _knowledge_base.is_built,
            "total_documents": len(_knowledge_base.documents),
            "documents_by_type": by_type,
            "embedding_model": settings.OPENAI_EMBEDDING_MODEL,
            "chat_model": settings.OPENAI_MODEL,
            "rag_top_k": settings.RAG_TOP_K,
            "similarity_threshold": settings.RAG_SIMILARITY_THRESHOLD,
            "scope_threshold": settings.RAG_SCOPE_THRESHOLD,
            "warning": (
                None
                if _knowledge_base.is_built
                else "Knowledge base has not been built in this worker yet. It builds "
                "on the first chat message, or call POST /api/v1/ai/refresh-knowledge."
            ),
            "note": (
                "The knowledge base is an in-memory snapshot per worker process. Content "
                "added through the admin panel is not recommended until a rebuild runs. "
                "With multiple workers, refresh or restart them all."
            ),
        }
