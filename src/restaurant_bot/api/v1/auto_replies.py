import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.engine import get_db
from restaurant_bot.auth.permissions import CurrentUser, require_owner
from restaurant_bot.services.auto_reply_service import (
    get_auto_replies, get_auto_reply, create_auto_reply,
    update_auto_reply, delete_auto_reply,
)

router = APIRouter(prefix="/restaurants/{restaurant_id}/auto-replies", tags=["auto-replies"])


class AutoReplyCreate(BaseModel):
    trigger_patterns: list[str] = Field(..., min_length=1, description="List of trigger words/phrases")
    response: str = Field(..., min_length=1, description="Response template. Use {restaurant_name}, {bot_name}, {address}, {phone}, etc.")
    category: str = Field("custom", description="Category: greeting, farewell, thanks, info, hours, custom")
    priority: int = Field(0, description="Higher priority = checked first")
    match_type: str = Field("keyword", description="'keyword' (any word matches) or 'exact' (full message must match)")


class AutoReplyUpdate(BaseModel):
    trigger_patterns: list[str] | None = None
    response: str | None = None
    category: str | None = None
    priority: int | None = None
    match_type: str | None = None
    is_active: bool | None = None


class AutoReplyResponse(BaseModel):
    id: uuid.UUID
    trigger_patterns: list[str]
    response: str
    category: str
    priority: int
    match_type: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AutoReplyResponse])
async def list_auto_replies(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    """List all auto-replies for this restaurant."""
    replies = await get_auto_replies(db, restaurant_id)
    return [AutoReplyResponse.model_validate(r) for r in replies]


@router.post("", response_model=AutoReplyResponse)
async def create_auto_reply_endpoint(
    restaurant_id: uuid.UUID,
    req: AutoReplyCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    """Create a new auto-reply. These respond instantly without using the AI (saves cost!)."""
    reply = await create_auto_reply(
        db, restaurant_id,
        trigger_patterns=req.trigger_patterns,
        response=req.response,
        category=req.category,
        priority=req.priority,
        match_type=req.match_type,
    )
    return AutoReplyResponse.model_validate(reply)


@router.get("/{reply_id}", response_model=AutoReplyResponse)
async def get_auto_reply_endpoint(
    restaurant_id: uuid.UUID,
    reply_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    reply = await get_auto_reply(db, restaurant_id, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Auto-reply not found")
    return AutoReplyResponse.model_validate(reply)


@router.patch("/{reply_id}", response_model=AutoReplyResponse)
async def update_auto_reply_endpoint(
    restaurant_id: uuid.UUID,
    reply_id: uuid.UUID,
    req: AutoReplyUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    """Update an auto-reply's patterns, response, or settings."""
    reply = await get_auto_reply(db, restaurant_id, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Auto-reply not found")
    updated = await update_auto_reply(db, reply, **req.model_dump(exclude_none=True))
    return AutoReplyResponse.model_validate(updated)


@router.delete("/{reply_id}")
async def delete_auto_reply_endpoint(
    restaurant_id: uuid.UUID,
    reply_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    """Delete an auto-reply."""
    reply = await get_auto_reply(db, restaurant_id, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Auto-reply not found")
    await delete_auto_reply(db, reply)
    return {"message": "Auto-reply deleted"}


@router.post("/test")
async def test_auto_reply(
    restaurant_id: uuid.UUID,
    message: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    """Test which auto-reply (if any) matches a given message. Useful for debugging patterns."""
    from restaurant_bot.services.auto_reply_service import check_auto_reply, match_auto_reply, get_auto_replies
    from restaurant_bot.services.config_service import config_service
    from sqlalchemy import select
    from restaurant_bot.db.models.restaurant import Restaurant

    result = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    config = await config_service.get_config(db, restaurant_id)

    # Check for match
    auto_replies = await get_auto_replies(db, restaurant_id)
    matched = match_auto_reply(message, auto_replies)

    if matched:
        from restaurant_bot.services.auto_reply_service import render_response
        rendered = render_response(matched.response, restaurant.name, config)
        return {
            "matched": True,
            "auto_reply_id": str(matched.id),
            "category": matched.category,
            "raw_response": matched.response,
            "rendered_response": rendered,
            "cost": "FREE - no LLM call",
        }
    else:
        return {
            "matched": False,
            "message": "No auto-reply matched. This message would be sent to the AI (costs API credits).",
            "cost": "PAID - LLM call required",
        }
