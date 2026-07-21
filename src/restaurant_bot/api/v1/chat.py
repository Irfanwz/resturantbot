import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.engine import get_db
from restaurant_bot.db.models.restaurant import Restaurant
from restaurant_bot.schemas.chat import ChatRequest, ChatResponse
from restaurant_bot.services.config_service import config_service
from restaurant_bot.session.base import ConversationSession
from restaurant_bot.session.memory import InMemorySessionStore
from restaurant_bot.agent.core import chat_with_agent
from restaurant_bot.agent.deps import RestaurantBotDeps
from restaurant_bot.db.models.conversation import ConversationLog
from restaurant_bot.services.auto_reply_service import check_auto_reply
from restaurant_bot.middleware.rate_limit import check_rate_limit

router = APIRouter(tags=["chat"])

# Global session store (will be replaced with Redis in production)
session_store = InMemorySessionStore(ttl_minutes=30)


@router.post("/restaurants/{restaurant_id}/chat", response_model=ChatResponse)
async def chat(
    restaurant_id: uuid.UUID,
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(check_rate_limit),
):
    from sqlalchemy import select

    # Verify restaurant exists
    result = await db.execute(
        select(Restaurant).where(Restaurant.id == restaurant_id, Restaurant.is_active == True)
    )
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    # Load config
    config = await config_service.get_config(db, restaurant_id)

    # Get or create session
    session_id = req.session_id or str(uuid.uuid4())
    session = await session_store.get(session_id)
    if session is None:
        session = ConversationSession(
            session_id=session_id,
            restaurant_id=restaurant_id,
        )

    # Build deps
    deps = RestaurantBotDeps(
        db=db,
        restaurant_id=restaurant_id,
        restaurant_name=restaurant.name,
        config=config,
        session=session,
    )

    # Check auto-replies first (FREE - no LLM call)
    auto_response = await check_auto_reply(
        db, restaurant_id, req.message, restaurant.name, config
    )

    if auto_response:
        reply = auto_response
    else:
        # No auto-reply matched — use AI agent (PAID - LLM call)
        try:
            reply = await chat_with_agent(deps, req.message)
        except Exception as e:
            import traceback
            traceback.print_exc()
            reply = config.ai.fallback_message

    # Log conversation
    try:
        db.add(ConversationLog(
            restaurant_id=restaurant_id,
            session_id=session_id,
            channel="rest_api",
            role="user",
            content=req.message,
        ))
        db.add(ConversationLog(
            restaurant_id=restaurant_id,
            session_id=session_id,
            channel="rest_api",
            role="assistant",
            content=reply,
        ))
    except Exception:
        pass  # Don't fail the chat if logging fails

    # Save session
    await session_store.save(session)

    # Build response
    cart_summary = None
    if not session.cart.is_empty:
        cart_summary = session.cart.to_dict()

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        cart_summary=cart_summary,
    )


@router.get("/restaurants/{restaurant_id}/widget-config")
async def get_widget_config(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — returns widget config (name, colors, quick replies). No auth needed."""
    from sqlalchemy import select

    result = await db.execute(
        select(Restaurant).where(Restaurant.id == restaurant_id, Restaurant.is_active == True)
    )
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    config = await config_service.get_config(db, restaurant_id)

    return {
        "restaurant_name": restaurant.name,
        "bot_name": config.ai.bot_name,
        "primary_color": config.branding.primary_color,
        "logo_url": config.branding.logo_url,
        "quick_replies": [
            {"emoji": qr.emoji, "label": qr.label, "message": qr.message}
            for qr in config.branding.quick_replies
        ],
    }
