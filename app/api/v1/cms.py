"""CMS endpoints for pages and blocks management."""

from typing import List
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.cms import CMSBlock, CMSPage
from app.schemas.cms import (
    CMSBlockCreate, CMSBlockReorderRequest, CMSBlockResponse, CMSBlockUpdate,
    CMSPageCreate, CMSPageListResponse, CMSPagePublicResponse, CMSPageResponse, CMSPageUpdate,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.utils.enums import CMSPageStatus

router = APIRouter()


# Public endpoints
@router.get("/pages/{slug}", response_model=CMSPagePublicResponse)
async def get_public_page(slug: str, db: DatabaseSession):
    """Get published page by slug (public)."""
    result = await db.execute(
        select(CMSPage)
        .options(selectinload(CMSPage.blocks))
        .where(CMSPage.slug == slug, CMSPage.is_published == True, CMSPage.is_deleted == False)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/menu")
async def get_menu(db: DatabaseSession):
    """Get navigation menu."""
    result = await db.execute(
        select(CMSPage)
        .where(CMSPage.show_in_menu == True, CMSPage.is_published == True, CMSPage.is_deleted == False)
        .order_by(CMSPage.menu_order)
    )
    pages = result.scalars().all()
    return {"items": [{"id": p.id, "title": p.title, "slug": p.slug, "url": f"/pages/{p.slug}"} for p in pages]}


# Admin endpoints
@router.get("/admin/pages", response_model=PaginatedResponse[CMSPageListResponse], dependencies=[RequireAdmin])
async def list_pages(db: DatabaseSession, page: int = Query(1), page_size: int = Query(20), status: CMSPageStatus = None):
    """List all pages (admin)."""
    query = select(CMSPage).where(CMSPage.is_deleted == False)
    if status:
        query = query.where(CMSPage.status == status.value)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(CMSPage.created_at.desc()).offset((page-1)*page_size).limit(page_size)
    result = await db.execute(query)
    pages = result.scalars().all()
    
    return PaginatedResponse.create(pages, total, page, page_size)


@router.post("/admin/pages", response_model=CMSPageResponse, dependencies=[RequireAdmin])
async def create_page(data: CMSPageCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new page (admin)."""
    page = CMSPage(
        title=data.title, slug=data.slug, description=data.description,
        template=data.template, status=data.status.value,
        meta_title=data.meta_title, meta_description=data.meta_description,
        show_in_menu=data.show_in_menu, menu_order=data.menu_order,
        requires_auth=data.requires_auth, created_by=current_user.id,
    )
    db.add(page)
    await db.flush()
    
    if data.blocks:
        for i, block_data in enumerate(data.blocks):
            block = CMSBlock(
                page_id=page.id, block_type=block_data.block_type.value,
                position=block_data.position or i, section=block_data.section,
                title=block_data.title, content=block_data.content,
                config=block_data.config, items=block_data.items,
                is_visible=block_data.is_visible, created_by=current_user.id,
            )
            db.add(block)
    
    await db.commit()
    await db.refresh(page)
    return page


@router.get("/admin/pages/{page_id}", response_model=CMSPageResponse, dependencies=[RequireAdmin])
async def get_page(page_id: UUID, db: DatabaseSession):
    """Get page by ID (admin)."""
    result = await db.execute(
        select(CMSPage).options(selectinload(CMSPage.blocks))
        .where(CMSPage.id == page_id, CMSPage.is_deleted == False)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.put("/admin/pages/{page_id}", response_model=CMSPageResponse, dependencies=[RequireAdmin])
async def update_page(page_id: UUID, data: CMSPageUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update page (admin)."""
    result = await db.execute(select(CMSPage).where(CMSPage.id == page_id, CMSPage.is_deleted == False))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"]:
        update_data["status"] = update_data["status"].value
    for field, value in update_data.items():
        setattr(page, field, value)
    page.updated_by = current_user.id
    
    await db.commit()
    await db.refresh(page)
    return page


@router.post("/admin/pages/{page_id}/publish", response_model=CMSPageResponse, dependencies=[RequireAdmin])
async def publish_page(page_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Publish a page (admin)."""
    result = await db.execute(select(CMSPage).where(CMSPage.id == page_id))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    from datetime import datetime, timezone
    page.status = CMSPageStatus.PUBLISHED.value
    page.is_published = True
    page.published_at = datetime.now(timezone.utc)
    page.updated_by = current_user.id
    await db.commit()
    return page


@router.delete("/admin/pages/{page_id}", dependencies=[RequireAdmin])
async def delete_page(page_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete page (admin)."""
    result = await db.execute(select(CMSPage).where(CMSPage.id == page_id))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    page.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Page deleted"}


# Block management
@router.post("/admin/pages/{page_id}/blocks", response_model=CMSBlockResponse, dependencies=[RequireAdmin])
async def add_block(page_id: UUID, data: CMSBlockCreate, current_user: CurrentUser, db: DatabaseSession):
    """Add block to page (admin)."""
    block = CMSBlock(
        page_id=page_id, block_type=data.block_type.value,
        position=data.position, section=data.section,
        title=data.title, content=data.content,
        config=data.config, items=data.items,
        is_visible=data.is_visible, created_by=current_user.id,
    )
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return block


@router.put("/admin/blocks/{block_id}", response_model=CMSBlockResponse, dependencies=[RequireAdmin])
async def update_block(block_id: UUID, data: CMSBlockUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update block (admin)."""
    result = await db.execute(select(CMSBlock).where(CMSBlock.id == block_id))
    block = result.scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    update_data = data.model_dump(exclude_unset=True)
    if "block_type" in update_data and update_data["block_type"]:
        update_data["block_type"] = update_data["block_type"].value
    for field, value in update_data.items():
        setattr(block, field, value)
    block.updated_by = current_user.id
    await db.commit()
    return block


@router.post("/admin/pages/{page_id}/reorder", dependencies=[RequireAdmin])
async def reorder_blocks(page_id: UUID, data: List[CMSBlockReorderRequest], db: DatabaseSession):
    """Reorder blocks on a page (admin)."""
    for item in data:
        result = await db.execute(select(CMSBlock).where(CMSBlock.id == item.block_id))
        block = result.scalar_one_or_none()
        if block:
            block.position = item.new_position
    await db.commit()
    return {"message": "Blocks reordered"}


@router.delete("/admin/blocks/{block_id}", dependencies=[RequireAdmin])
async def delete_block(block_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete block (admin)."""
    result = await db.execute(select(CMSBlock).where(CMSBlock.id == block_id))
    block = result.scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    block.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Block deleted"}
