"""Service for doctor-patient document sharing."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.shared_document import DocumentComment, SharedDocument
from app.models.user import User
from app.schemas.shared_document import DocumentCommentCreate, SendDocumentRequest
from app.utils.notifications import notify

logger = get_logger(__name__)


class SharedDocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Send document ──────────────────────────────────────────

    async def send_document(
        self, sender_id: UUID, data: SendDocumentRequest
    ) -> SharedDocument:
        """Send a document from one user to another."""
        doc = SharedDocument(
            sender_id=sender_id,
            receiver_id=data.receiver_id,
            document_id=data.document_id,
            consultation_id=data.consultation_id,
            title=data.title,
            file_name=data.file_name,
            file_url=data.file_url,
            file_type=data.file_type,
            file_size=data.file_size,
            document_type=data.document_type,
            description=data.description,
            is_viewed=False,
            created_by=sender_id,
        )
        self.db.add(doc)
        await self.db.flush()
        logger.info(
            "document_sent",
            doc_id=str(doc.id),
            sender=str(sender_id),
            receiver=str(data.receiver_id),
        )

        # Notify receiver about the shared document
        try:
            sender_result = await self.db.execute(
                select(User.full_name).where(User.id == sender_id)
            )
            sender_row = sender_result.scalar_one_or_none()
            sender_name = sender_row or "Someone"
            await notify(
                db=self.db,
                user_id=data.receiver_id,
                title="Document Shared",
                message=f"{sender_name} shared a document: {data.title or data.file_name}",
                notification_type="info",
                entity_type="shared_document",
                entity_id=doc.id,
                action_url=f"/documents/shared/{doc.id}",
                created_by=sender_id,
            )
        except Exception as exc:
            logger.error("document_share_notification_failed", error=str(exc))

        return doc

    # ── List sent ──────────────────────────────────────────────

    async def list_sent(
        self, user_id: UUID, page: int = 1, page_size: int = 20
    ) -> Tuple[list, int]:
        """List documents sent by the user."""
        return await self._list_documents(
            filter_col=SharedDocument.sender_id,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )

    # ── List received ──────────────────────────────────────────

    async def list_received(
        self, user_id: UUID, page: int = 1, page_size: int = 20
    ) -> Tuple[list, int]:
        """List documents received by the user."""
        return await self._list_documents(
            filter_col=SharedDocument.receiver_id,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )

    # ── Shared list logic ──────────────────────────────────────

    async def _list_documents(
        self, filter_col, user_id: UUID, page: int, page_size: int
    ) -> Tuple[list, int]:
        # Count
        count_q = await self.db.execute(
            select(func.count(SharedDocument.id)).where(
                filter_col == user_id,
                SharedDocument.is_deleted == False,
            )
        )
        total = count_q.scalar() or 0

        # Fetch
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(SharedDocument)
            .where(filter_col == user_id, SharedDocument.is_deleted == False)
            .order_by(SharedDocument.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        docs = result.scalars().all()

        # Bulk lookup user names
        all_user_ids = set()
        for d in docs:
            all_user_ids.add(d.sender_id)
            all_user_ids.add(d.receiver_id)

        names = {}
        if all_user_ids:
            name_result = await self.db.execute(
                select(User.id, User.full_name).where(User.id.in_(all_user_ids))
            )
            names = {row.id: row.full_name for row in name_result.all()}

        items = []
        for d in docs:
            # Comment count + latest comment
            comment_q = await self.db.execute(
                select(func.count(DocumentComment.id)).where(
                    DocumentComment.shared_document_id == d.id,
                    DocumentComment.is_deleted == False,
                )
            )
            comment_count = comment_q.scalar() or 0

            latest_comment = None
            if comment_count > 0:
                lc = await self.db.execute(
                    select(DocumentComment.content)
                    .where(
                        DocumentComment.shared_document_id == d.id,
                        DocumentComment.is_deleted == False,
                    )
                    .order_by(DocumentComment.created_at.desc())
                    .limit(1)
                )
                latest_comment = lc.scalar_one_or_none()

            items.append(
                {
                    "id": d.id,
                    "sender_id": d.sender_id,
                    "receiver_id": d.receiver_id,
                    "title": d.title,
                    "file_name": d.file_name,
                    "file_url": d.file_url,
                    "file_type": d.file_type,
                    "file_size": d.file_size,
                    "document_type": d.document_type,
                    "is_viewed": d.is_viewed,
                    "viewed_at": d.viewed_at,
                    "created_at": d.created_at,
                    "sender_name": names.get(d.sender_id),
                    "receiver_name": names.get(d.receiver_id),
                    "comment_count": comment_count,
                    "latest_comment": latest_comment,
                }
            )

        return items, total

    # ── Get detail ─────────────────────────────────────────────

    async def get_by_id(self, doc_id: UUID) -> Optional[SharedDocument]:
        result = await self.db.execute(
            select(SharedDocument).where(
                SharedDocument.id == doc_id, SharedDocument.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def get_detail(self, doc_id: UUID) -> Optional[dict]:
        """Get document with sender/receiver names and comments."""
        doc = await self.get_by_id(doc_id)
        if not doc:
            return None

        # Names
        user_ids = {doc.sender_id, doc.receiver_id}
        name_result = await self.db.execute(
            select(User.id, User.full_name).where(User.id.in_(user_ids))
        )
        names = {row.id: row.full_name for row in name_result.all()}

        # Comments
        comments_q = await self.db.execute(
            select(DocumentComment)
            .where(
                DocumentComment.shared_document_id == doc.id,
                DocumentComment.is_deleted == False,
            )
            .order_by(DocumentComment.created_at.asc())
        )
        comments = comments_q.scalars().all()

        # Comment user names
        comment_user_ids = {c.user_id for c in comments}
        comment_names = {}
        if comment_user_ids:
            cn = await self.db.execute(
                select(User.id, User.full_name).where(User.id.in_(comment_user_ids))
            )
            comment_names = {row.id: row.full_name for row in cn.all()}

        return {
            "id": doc.id,
            "sender_id": doc.sender_id,
            "receiver_id": doc.receiver_id,
            "document_id": doc.document_id,
            "consultation_id": doc.consultation_id,
            "title": doc.title,
            "file_name": doc.file_name,
            "file_url": doc.file_url,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "document_type": doc.document_type,
            "description": doc.description,
            "is_viewed": doc.is_viewed,
            "viewed_at": doc.viewed_at,
            "created_at": doc.created_at,
            "sender_name": names.get(doc.sender_id),
            "receiver_name": names.get(doc.receiver_id),
            "comment_count": len(comments),
            "comments": [
                {
                    "id": c.id,
                    "shared_document_id": c.shared_document_id,
                    "user_id": c.user_id,
                    "content": c.content,
                    "created_at": c.created_at,
                    "user_name": comment_names.get(c.user_id),
                }
                for c in comments
            ],
        }

    # ── Mark viewed ────────────────────────────────────────────

    async def mark_viewed(self, doc_id: UUID) -> None:
        """Mark a document as viewed by the receiver."""
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(SharedDocument)
            .where(SharedDocument.id == doc_id)
            .values(is_viewed=True, viewed_at=now)
        )

    # ── Add comment ────────────────────────────────────────────

    async def add_comment(
        self, doc_id: UUID, user_id: UUID, data: DocumentCommentCreate
    ) -> dict:
        """Add a comment to a shared document."""
        comment = DocumentComment(
            shared_document_id=doc_id,
            user_id=user_id,
            content=data.content,
            created_by=user_id,
        )
        self.db.add(comment)
        await self.db.flush()

        # Get user name
        u = await self.db.execute(
            select(User.full_name).where(User.id == user_id)
        )
        user_name = u.scalar_one_or_none() or "Unknown"

        logger.info("document_comment_added", doc_id=str(doc_id), user=str(user_id))

        return {
            "id": comment.id,
            "shared_document_id": doc_id,
            "user_id": user_id,
            "content": comment.content,
            "created_at": comment.created_at,
            "user_name": user_name,
        }

    # ── Stats ──────────────────────────────────────────────────

    async def get_stats(self, user_id: UUID) -> dict:
        """Get sent/received/unviewed counts."""
        sent_q = await self.db.execute(
            select(func.count(SharedDocument.id)).where(
                SharedDocument.sender_id == user_id,
                SharedDocument.is_deleted == False,
            )
        )
        received_q = await self.db.execute(
            select(func.count(SharedDocument.id)).where(
                SharedDocument.receiver_id == user_id,
                SharedDocument.is_deleted == False,
            )
        )
        unviewed_q = await self.db.execute(
            select(func.count(SharedDocument.id)).where(
                SharedDocument.receiver_id == user_id,
                SharedDocument.is_viewed == False,
                SharedDocument.is_deleted == False,
            )
        )
        return {
            "sent_count": sent_q.scalar() or 0,
            "received_count": received_q.scalar() or 0,
            "unviewed_count": unviewed_q.scalar() or 0,
        }
