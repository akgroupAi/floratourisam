"""Blog comment service."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.site import BlogComment, BlogPost
from app.schemas.site import BlogCommentCreate, BlogCommentResponse, BlogCommentUpdate

logger = get_logger(__name__)


class BlogCommentService:
    """Service for blog post comments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_by_id(self, comment_id: UUID) -> Optional[BlogComment]:
        result = await self.db.execute(
            select(BlogComment)
            .options(selectinload(BlogComment.user), selectinload(BlogComment.replies))
            .where(BlogComment.id == comment_id, BlogComment.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_for_post(
        self,
        post_id: UUID,
        approved_only: bool = True,
    ) -> List[BlogCommentResponse]:
        """Return threaded top-level comments for a post, with replies nested."""
        query = (
            select(BlogComment)
            .options(
                selectinload(BlogComment.user),
                selectinload(BlogComment.replies).selectinload(BlogComment.user),
            )
            .where(
                BlogComment.post_id == post_id,
                BlogComment.parent_id == None,  # noqa: E711 — top-level only
                BlogComment.is_deleted == False,
            )
            .order_by(BlogComment.created_at.asc())
        )
        if approved_only:
            query = query.where(BlogComment.is_approved == True)

        rows = list((await self.db.execute(query)).scalars().all())
        return [self._to_response(c, approved_only=approved_only) for c in rows]

    async def get_all_for_post(
        self,
        post_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[BlogCommentResponse], int]:
        """Admin: all comments (any status) for a post, paginated."""
        base_q = select(BlogComment).where(
            BlogComment.post_id == post_id,
            BlogComment.parent_id == None,  # noqa: E711
            BlogComment.is_deleted == False,
        )
        total = (await self.db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0

        rows = list(
            (
                await self.db.execute(
                    base_q.options(
                        selectinload(BlogComment.user),
                        selectinload(BlogComment.replies).selectinload(BlogComment.user),
                    )
                    .order_by(BlogComment.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars().all()
        )
        return [self._to_response(c, approved_only=False) for c in rows], total

    async def count_approved(self, post_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                BlogComment.post_id == post_id,
                BlogComment.is_approved == True,
                BlogComment.is_deleted == False,
            )
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def create(
        self,
        post_id: UUID,
        data: BlogCommentCreate,
        user_id: Optional[UUID] = None,
    ) -> BlogCommentResponse:
        """Submit a new comment. Guest comments default to is_approved=False."""
        # Validate parent if provided
        if data.parent_id:
            parent = await self.db.execute(
                select(BlogComment).where(
                    BlogComment.id == data.parent_id,
                    BlogComment.post_id == post_id,
                    BlogComment.parent_id == None,  # noqa: E711 — only 1 level deep
                    BlogComment.is_deleted == False,
                )
            )
            if not parent.scalar_one_or_none():
                raise ValueError("Parent comment not found or does not belong to this post")

        # Guest must supply name
        if not user_id and not data.guest_name:
            raise ValueError("guest_name is required for unauthenticated comments")

        # Authenticated user comments are auto-approved; guest comments await moderation
        is_approved = user_id is not None

        comment = BlogComment(
            post_id=post_id,
            user_id=user_id,
            parent_id=data.parent_id,
            guest_name=data.guest_name,
            guest_email=data.guest_email,
            content=data.content,
            is_approved=is_approved,
            created_by=user_id,
        )
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)
        logger.info("blog_comment_created", post_id=str(post_id), comment_id=str(comment.id), approved=is_approved)
        return self._to_response(comment)

    async def update(
        self,
        comment: BlogComment,
        data: BlogCommentUpdate,
        updated_by: Optional[UUID] = None,
    ) -> BlogCommentResponse:
        comment.content = data.content
        comment.updated_by = updated_by
        await self.db.commit()
        await self.db.refresh(comment)
        return self._to_response(comment)

    async def approve(self, comment: BlogComment, updated_by: Optional[UUID] = None) -> BlogCommentResponse:
        comment.is_approved = True
        comment.updated_by = updated_by
        await self.db.commit()
        await self.db.refresh(comment)
        logger.info("blog_comment_approved", comment_id=str(comment.id))
        return self._to_response(comment)

    async def unapprove(self, comment: BlogComment, updated_by: Optional[UUID] = None) -> BlogCommentResponse:
        comment.is_approved = False
        comment.updated_by = updated_by
        await self.db.commit()
        await self.db.refresh(comment)
        return self._to_response(comment)

    async def delete(self, comment: BlogComment, deleted_by: Optional[UUID] = None) -> None:
        comment.soft_delete(deleted_by=deleted_by)
        await self.db.commit()
        logger.info("blog_comment_deleted", comment_id=str(comment.id))

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _to_response(self, c: BlogComment, approved_only: bool = True) -> BlogCommentResponse:
        replies = []
        for r in (c.replies or []):
            if r.is_deleted:
                continue
            if approved_only and not r.is_approved:
                continue
            replies.append(
                BlogCommentResponse(
                    id=r.id,
                    post_id=r.post_id,
                    parent_id=r.parent_id,
                    user_id=r.user_id,
                    author_name=r.author_name,
                    author_avatar=r.author_avatar,
                    content=r.content,
                    is_approved=r.is_approved,
                    replies=[],
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
            )
        return BlogCommentResponse(
            id=c.id,
            post_id=c.post_id,
            parent_id=c.parent_id,
            user_id=c.user_id,
            author_name=c.author_name,
            author_avatar=c.author_avatar,
            content=c.content,
            is_approved=c.is_approved,
            replies=replies,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
