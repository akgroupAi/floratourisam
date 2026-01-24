"""AI service."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.ai_log import AIConversation, AILog

logger = get_logger(__name__)


class AIService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_conversation(self, user_id: UUID, context_type: Optional[str] = None) -> AIConversation:
        conv = AIConversation(
            user_id=user_id, session_id=str(uuid4()),
            context_type=context_type, is_active=True,
        )
        self.db.add(conv)
        await self.db.commit()
        await self.db.refresh(conv)
        return conv

    async def log_interaction(
        self, conv_id: UUID, user_id: UUID, user_msg: str,
        ai_response: str, model: str, tokens: int = 0,
    ) -> AILog:
        log = AILog(
            conversation_id=conv_id, user_id=user_id,
            user_message=user_msg, ai_response=ai_response,
            model_name=model, total_tokens=tokens,
            prompt_tokens=tokens//2, completion_tokens=tokens//2,
            response_time_ms=100,
        )
        self.db.add(log)
        await self.db.commit()
        return log
