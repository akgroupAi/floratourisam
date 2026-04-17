"""Chat service — business logic for chat rooms and messages."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.chat import ChatMessage, ChatParticipant, ChatRoom
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatRoomCreate
from app.schemas.common import PaginationParams
from app.utils.notifications import notify

logger = get_logger(__name__)


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Rooms ──────────────────────────────────────────────────────

    async def create_room(
        self, data: ChatRoomCreate, created_by: UUID
    ) -> ChatRoom:
        """Create a chat room and add participants."""
        now = datetime.now(timezone.utc)

        room = ChatRoom(
            name=data.name,
            room_type=data.room_type.value,
            consultation_id=data.consultation_id,
            is_active=True,
            message_count=0,
            created_by=created_by,
        )
        self.db.add(room)
        await self.db.flush()

        # Add creator as admin participant
        all_user_ids = set(data.participant_ids)
        all_user_ids.add(created_by)

        for uid in all_user_ids:
            participant = ChatParticipant(
                room_id=room.id,
                user_id=uid,
                is_active=True,
                joined_at=now,
                role="admin" if uid == created_by else "member",
                created_by=created_by,
            )
            self.db.add(participant)

        await self.db.flush()
        logger.info("chat_room_created", room_id=str(room.id), type=room.room_type)
        return room

    async def get_or_create_direct_room(
        self, user_id_1: UUID, user_id_2: UUID, consultation_id: Optional[UUID] = None
    ) -> ChatRoom:
        """Get existing consultation room between two users, or create one."""
        # Check for existing active room between these two users
        result = await self.db.execute(
            select(ChatRoom)
            .join(ChatParticipant, ChatParticipant.room_id == ChatRoom.id)
            .where(
                ChatRoom.is_active == True,
                ChatRoom.is_deleted == False,
                ChatRoom.room_type == "consultation",
                ChatParticipant.user_id == user_id_1,
                ChatParticipant.is_active == True,
            )
        )
        rooms_for_user1 = result.scalars().all()

        for room in rooms_for_user1:
            # Check if user_id_2 is also a participant
            p2 = await self.db.execute(
                select(ChatParticipant).where(
                    ChatParticipant.room_id == room.id,
                    ChatParticipant.user_id == user_id_2,
                    ChatParticipant.is_active == True,
                    ChatParticipant.is_deleted == False,
                )
            )
            if p2.scalar_one_or_none():
                return room

        # No existing room — create one
        now = datetime.now(timezone.utc)
        room = ChatRoom(
            room_type="consultation",
            consultation_id=consultation_id,
            is_active=True,
            message_count=0,
            created_by=user_id_1,
        )
        self.db.add(room)
        await self.db.flush()

        for uid, role in [(user_id_1, "admin"), (user_id_2, "member")]:
            self.db.add(
                ChatParticipant(
                    room_id=room.id,
                    user_id=uid,
                    is_active=True,
                    joined_at=now,
                    role=role,
                    created_by=user_id_1,
                )
            )
        await self.db.flush()
        logger.info("direct_room_created", room_id=str(room.id))
        return room

    async def list_rooms_for_user(self, user_id: UUID) -> Tuple[list, int]:
        """Return all active rooms the user participates in, with unread counts."""
        result = await self.db.execute(
            select(ChatRoom, ChatParticipant.unread_count)
            .join(ChatParticipant, ChatParticipant.room_id == ChatRoom.id)
            .where(
                ChatParticipant.user_id == user_id,
                ChatParticipant.is_active == True,
                ChatParticipant.is_deleted == False,
                ChatRoom.is_active == True,
                ChatRoom.is_deleted == False,
            )
            .order_by(ChatRoom.last_message_at.desc().nullslast(), ChatRoom.created_at.desc())
        )
        rows = result.all()

        rooms = []
        total_unread = 0
        for room, unread in rows:
            # Count participants
            p_count = await self.db.execute(
                select(func.count(ChatParticipant.id)).where(
                    ChatParticipant.room_id == room.id,
                    ChatParticipant.is_active == True,
                    ChatParticipant.is_deleted == False,
                )
            )
            participant_count = p_count.scalar() or 0

            rooms.append(
                {
                    "id": room.id,
                    "name": room.name,
                    "room_type": room.room_type,
                    "consultation_id": room.consultation_id,
                    "is_active": room.is_active,
                    "last_message_at": room.last_message_at,
                    "message_count": room.message_count,
                    "created_at": room.created_at,
                    "participant_count": participant_count,
                    "unread_count": unread,
                }
            )
            total_unread += unread

        return rooms, total_unread

    async def get_room_by_id(self, room_id: UUID) -> Optional[ChatRoom]:
        result = await self.db.execute(
            select(ChatRoom).where(
                ChatRoom.id == room_id, ChatRoom.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def is_participant(self, room_id: UUID, user_id: UUID) -> bool:
        result = await self.db.execute(
            select(ChatParticipant.id).where(
                ChatParticipant.room_id == room_id,
                ChatParticipant.user_id == user_id,
                ChatParticipant.is_active == True,
                ChatParticipant.is_deleted == False,
            )
        )
        return result.scalar_one_or_none() is not None

    # ── Messages ───────────────────────────────────────────────────

    async def send_message(
        self, room_id: UUID, sender_id: UUID, data: ChatMessageCreate
    ) -> dict:
        """Persist a message and update room counters."""
        now = datetime.now(timezone.utc)

        message = ChatMessage(
            room_id=room_id,
            sender_id=sender_id,
            message_type=data.message_type.value if hasattr(data.message_type, "value") else data.message_type,
            content=data.content,
            reply_to_id=data.reply_to_id,
            file_url=data.file_url,
            file_name=data.file_name,
            file_type=data.file_type,
            file_size_bytes=data.file_size_bytes,
            created_by=sender_id,
        )
        self.db.add(message)
        await self.db.flush()

        # Update room counters
        await self.db.execute(
            update(ChatRoom)
            .where(ChatRoom.id == room_id)
            .values(
                last_message_at=now,
                message_count=ChatRoom.message_count + 1,
            )
        )

        # Increment unread for all participants except sender
        await self.db.execute(
            update(ChatParticipant)
            .where(
                ChatParticipant.room_id == room_id,
                ChatParticipant.user_id != sender_id,
                ChatParticipant.is_active == True,
            )
            .values(unread_count=ChatParticipant.unread_count + 1)
        )

        # Fetch sender info
        sender = await self.db.execute(
            select(User.full_name, User.avatar_url).where(User.id == sender_id)
        )
        sender_row = sender.one_or_none()
        sender_name = sender_row.full_name if sender_row else "Unknown"
        sender_avatar = sender_row.avatar_url if sender_row else None

        logger.info("chat_message_sent", room_id=str(room_id), sender=str(sender_id))

        # Notify all other participants in the room (best-effort)
        try:
            participants_result = await self.db.execute(
                select(ChatParticipant.user_id).where(
                    ChatParticipant.room_id == room_id,
                    ChatParticipant.user_id != sender_id,
                    ChatParticipant.is_active == True,
                )
            )
            for row in participants_result.all():
                await notify(
                    db=self.db,
                    user_id=row.user_id,
                    title="New Message",
                    message=f"{sender_name}: {(data.content or 'sent a file')[:80]}",
                    notification_type="info",
                    entity_type="chat_room",
                    entity_id=room_id,
                    action_url=f"/chat/{room_id}",
                    created_by=sender_id,
                )
        except Exception as exc:
            logger.error("chat_notification_failed", error=str(exc))

        return {
            "id": str(message.id),
            "room_id": str(room_id),
            "sender_id": str(sender_id),
            "sender_name": sender_name,
            "sender_avatar": sender_avatar,
            "message_type": message.message_type,
            "content": message.content,
            "file_url": message.file_url,
            "file_name": message.file_name,
            "file_type": message.file_type,
            "file_size_bytes": message.file_size_bytes,
            "reply_to_id": str(message.reply_to_id) if message.reply_to_id else None,
            "is_edited": False,
            "edited_at": None,
            "created_at": message.created_at.isoformat() if message.created_at else now.isoformat(),
        }

    async def get_messages(self, room_id: UUID) -> list:
        """Get all messages for a room in chronological order."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.room_id == room_id,
                ChatMessage.is_deleted == False,
            )
            .order_by(ChatMessage.created_at.asc())
        )
        messages = result.scalars().all()

        # Collect sender IDs for bulk name lookup
        sender_ids = {m.sender_id for m in messages}
        names = {}
        avatars = {}
        if sender_ids:
            name_result = await self.db.execute(
                select(User.id, User.full_name, User.avatar_url).where(User.id.in_(sender_ids))
            )
            user_rows = name_result.all()
            names = {row.id: row.full_name for row in user_rows}
            avatars = {row.id: row.avatar_url for row in user_rows}

        items = []
        for m in messages:
            items.append(
                {
                    "id": m.id,
                    "room_id": m.room_id,
                    "sender_id": m.sender_id,
                    "message_type": m.message_type,
                    "content": m.content,
                    "file_url": m.file_url,
                    "file_name": m.file_name,
                    "file_type": m.file_type,
                    "file_size_bytes": m.file_size_bytes,
                    "reply_to_id": m.reply_to_id,
                    "is_edited": m.is_edited,
                    "edited_at": m.edited_at,
                    "created_at": m.created_at,
                    "sender_name": names.get(m.sender_id, "Unknown"),
                    "sender_avatar": avatars.get(m.sender_id),
                    "reply_to_content": None,
                }
            )

        return items

    # ── Read receipts ──────────────────────────────────────────────

    async def mark_read(self, room_id: UUID, user_id: UUID) -> None:
        """Mark all messages in the room as read for this user."""
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(ChatParticipant)
            .where(
                ChatParticipant.room_id == room_id,
                ChatParticipant.user_id == user_id,
                ChatParticipant.is_active == True,
            )
            .values(unread_count=0, last_read_at=now)
        )
