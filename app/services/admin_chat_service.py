"""Admin oversight of doctor/patient chat.

Reading patient conversations is sensitive. Every access through this service is
logged with the acting admin so the access itself is auditable.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.chat import ChatMessage, ChatParticipant, ChatRoom
from app.models.user import User
from app.schemas.common import PaginationParams

logger = get_logger(__name__)


class AdminChatService:
    """Read-only chat access plus message moderation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_rooms(
        self,
        pagination: PaginationParams,
        room_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        participant_id: Optional[UUID] = None,
        consultation_id: Optional[UUID] = None,
        search: Optional[str] = None,
        from_date=None,
        to_date=None,
    ) -> Tuple[List[dict], int]:
        """List chat rooms with participant names attached."""
        filters = [ChatRoom.is_deleted == False]
        if room_type:
            filters.append(ChatRoom.room_type == room_type)
        if is_active is not None:
            filters.append(ChatRoom.is_active == is_active)
        if consultation_id:
            filters.append(ChatRoom.consultation_id == consultation_id)
        if participant_id:
            filters.append(
                ChatRoom.id.in_(
                    select(ChatParticipant.room_id).where(
                        ChatParticipant.user_id == participant_id
                    )
                )
            )
        if search:
            filters.append(ChatRoom.name.ilike(f"%{search}%"))
        if from_date:
            filters.append(
                ChatRoom.created_at
                >= datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
            )
        if to_date:
            filters.append(
                ChatRoom.created_at
                < datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)
                + timedelta(days=1)
            )

        total = (
            await self.db.execute(
                select(func.count()).select_from(select(ChatRoom.id).where(*filters).subquery())
            )
        ).scalar() or 0

        rooms = list(
            (
                await self.db.execute(
                    select(ChatRoom)
                    .where(*filters)
                    .order_by(
                        func.coalesce(ChatRoom.last_message_at, ChatRoom.created_at).desc()
                    )
                    .offset(pagination.offset)
                    .limit(pagination.page_size)
                )
            )
            .scalars()
            .all()
        )
        if not rooms:
            return [], total

        room_ids = [room.id for room in rooms]
        participant_rows = (
            await self.db.execute(
                select(ChatParticipant.room_id, User.id, User.full_name, User.email, User.role)
                .join(User, ChatParticipant.user_id == User.id)
                .where(ChatParticipant.room_id.in_(room_ids))
            )
        ).all()

        participants: dict[UUID, list] = {room_id: [] for room_id in room_ids}
        for room_id, user_id, full_name, email, role in participant_rows:
            participants[room_id].append({
                "user_id": user_id,
                "name": full_name,
                "email": email,
                "role": role,
            })

        return [
            {
                "id": room.id,
                "name": room.name,
                "room_type": room.room_type,
                "consultation_id": room.consultation_id,
                "is_active": room.is_active,
                "message_count": room.message_count or 0,
                "last_message_at": room.last_message_at,
                "closed_at": room.closed_at,
                "participants": participants.get(room.id, []),
                "created_at": room.created_at,
            }
            for room in rooms
        ], total

    async def get_room(self, room_id: UUID) -> Optional[ChatRoom]:
        result = await self.db.execute(
            select(ChatRoom).where(ChatRoom.id == room_id, ChatRoom.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_messages(
        self,
        room_id: UUID,
        pagination: PaginationParams,
        accessed_by: UUID,
        search: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Tuple[List[dict], int]:
        """Full transcript for one room, oldest first. Logs the access."""
        filters = [ChatMessage.room_id == room_id]
        if not include_deleted:
            filters.append(ChatMessage.is_deleted == False)
        if search:
            filters.append(ChatMessage.content.ilike(f"%{search}%"))

        total = (
            await self.db.execute(
                select(func.count()).select_from(
                    select(ChatMessage.id).where(*filters).subquery()
                )
            )
        ).scalar() or 0

        rows = (
            await self.db.execute(
                select(ChatMessage, User.full_name, User.email, User.role)
                .outerjoin(User, ChatMessage.sender_id == User.id)
                .where(*filters)
                .order_by(ChatMessage.created_at.asc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).all()

        # Reading a patient conversation is itself an auditable event.
        logger.info(
            "admin_chat_transcript_accessed",
            room_id=str(room_id),
            accessed_by=str(accessed_by),
            message_count=len(rows),
        )

        return [
            {
                "id": message.id,
                "room_id": message.room_id,
                "sender_id": message.sender_id,
                "sender_name": name,
                "sender_email": email,
                "sender_role": role,
                "message_type": message.message_type,
                "content": message.content,
                "file_url": message.file_url,
                "file_name": message.file_name,
                "is_edited": message.is_edited,
                "is_deleted": message.is_deleted,
                "created_at": message.created_at,
            }
            for message, name, email, role in rows
        ], total

    async def get_stats(self) -> dict:
        """Room and message volume, plus how much traffic is recent."""
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        total_rooms = (
            await self.db.execute(
                select(func.count(ChatRoom.id)).where(ChatRoom.is_deleted == False)
            )
        ).scalar() or 0
        active_rooms = (
            await self.db.execute(
                select(func.count(ChatRoom.id)).where(
                    ChatRoom.is_deleted == False, ChatRoom.is_active == True
                )
            )
        ).scalar() or 0
        rooms_by_type = dict(
            (
                await self.db.execute(
                    select(ChatRoom.room_type, func.count(ChatRoom.id))
                    .where(ChatRoom.is_deleted == False)
                    .group_by(ChatRoom.room_type)
                )
            ).all()
        )

        total_messages = (
            await self.db.execute(
                select(func.count(ChatMessage.id)).where(ChatMessage.is_deleted == False)
            )
        ).scalar() or 0
        messages_24h = (
            await self.db.execute(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.is_deleted == False, ChatMessage.created_at >= day_ago
                )
            )
        ).scalar() or 0
        messages_7d = (
            await self.db.execute(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.is_deleted == False, ChatMessage.created_at >= week_ago
                )
            )
        ).scalar() or 0
        active_rooms_24h = (
            await self.db.execute(
                select(func.count(ChatRoom.id)).where(
                    ChatRoom.is_deleted == False, ChatRoom.last_message_at >= day_ago
                )
            )
        ).scalar() or 0

        return {
            "total_rooms": total_rooms,
            "active_rooms": active_rooms,
            "rooms_active_last_24h": active_rooms_24h,
            "rooms_by_type": rooms_by_type,
            "total_messages": total_messages,
            "messages_last_24h": messages_24h,
            "messages_last_7d": messages_7d,
            "average_messages_per_room": round(total_messages / total_rooms, 1)
            if total_rooms
            else 0.0,
        }

    async def delete_message(self, message_id: UUID, deleted_by: UUID, reason: str) -> bool:
        """Soft-delete an abusive or mistaken message. Returns False if not found."""
        result = await self.db.execute(
            select(ChatMessage).where(
                ChatMessage.id == message_id, ChatMessage.is_deleted == False
            )
        )
        message = result.scalar_one_or_none()
        if not message:
            return False

        message.soft_delete(deleted_by)
        metadata = dict(message.message_metadata or {})
        metadata["moderation"] = {
            "reason": reason,
            "deleted_by": str(deleted_by),
            "deleted_at": datetime.now(timezone.utc).isoformat(),
        }
        message.message_metadata = metadata

        await self.db.commit()
        logger.info(
            "admin_chat_message_deleted",
            message_id=str(message_id),
            deleted_by=str(deleted_by),
            reason=reason,
        )
        return True
