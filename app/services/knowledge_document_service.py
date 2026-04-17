"""Knowledge Document service."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.knowledge_document import KnowledgeDocument
from app.schemas.knowledge_document import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentUpdate,
)

logger = get_logger(__name__)


class KnowledgeDocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: KnowledgeDocumentCreate, created_by: UUID) -> KnowledgeDocument:
        doc = KnowledgeDocument(**data.model_dump(), created_by=created_by)
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        logger.info("knowledge_doc_created", id=str(doc.id), title=data.title)
        return doc

    async def update(
        self, doc_id: UUID, data: KnowledgeDocumentUpdate, updated_by: UUID
    ) -> KnowledgeDocument:
        doc = await self._get(doc_id)
        if not doc:
            raise ValueError("Knowledge document not found")
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(doc, field, value)
        doc.updated_by = updated_by
        await self.db.commit()
        await self.db.refresh(doc)
        logger.info("knowledge_doc_updated", id=str(doc_id))
        return doc

    async def delete(self, doc_id: UUID, deleted_by: UUID) -> None:
        doc = await self._get(doc_id)
        if not doc:
            raise ValueError("Knowledge document not found")
        doc.soft_delete(deleted_by=deleted_by)
        await self.db.commit()
        logger.info("knowledge_doc_deleted", id=str(doc_id))

    async def get(self, doc_id: UUID) -> Optional[KnowledgeDocument]:
        return await self._get(doc_id)

    async def list_docs(
        self,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        active_only: bool = False,
        search: Optional[str] = None,
    ) -> tuple[List[KnowledgeDocument], int]:
        query = select(KnowledgeDocument).where(KnowledgeDocument.is_deleted == False)
        if active_only:
            query = query.where(KnowledgeDocument.is_active == True)
        if category:
            query = query.where(KnowledgeDocument.category == category)
        if search:
            query = query.where(
                KnowledgeDocument.title.ilike(f"%{search}%")
                | KnowledgeDocument.content.ilike(f"%{search}%")
            )

        total = (await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )).scalar() or 0

        query = (
            query.order_by(KnowledgeDocument.sort_order.asc(), KnowledgeDocument.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await self.db.execute(query)
        return list(rows.scalars().all()), total

    async def get_categories(self) -> List[str]:
        result = await self.db.execute(
            select(KnowledgeDocument.category)
            .where(KnowledgeDocument.is_deleted == False, KnowledgeDocument.is_active == True)
            .distinct()
            .order_by(KnowledgeDocument.category)
        )
        return [row[0] for row in result.all()]

    async def _get(self, doc_id: UUID) -> Optional[KnowledgeDocument]:
        result = await self.db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == doc_id,
                KnowledgeDocument.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()
