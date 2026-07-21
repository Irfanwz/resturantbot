import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.engine import get_db
from restaurant_bot.db.models.restaurant import Restaurant
from restaurant_bot.channels.whatsapp import WhatsAppAdapter
from restaurant_bot.channels.telegram import TelegramAdapter
from restaurant_bot.channels.base import OutgoingMessage
from restaurant_bot.services.config_service import config_service
from restaurant_bot.services.auto_reply_service import check_auto_reply
from restaurant_bot.session.base import ConversationSession
from restaurant_bot.session.memory import InMemorySessionStore
from restaurant_bot.agent.core import chat_with_agent
from restaurant_bot.agent.deps import RestaurantBotDeps
from restaurant_bot.schemas.config import RestaurantConfig
from restaurant_bot.db.models.conversation import ConversationLog
from restaurant_bot.auth.permissions import require_owner, CurrentUser

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Session stores
wa_session_store = InMemorySessionStore(ttl_minutes=60)
tg_session_store = InMemorySessionStore(ttl_minutes=60)

wa_adapter = WhatsAppAdapter()
tg_adapter = TelegramAdapter()


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification endpoint."""
    # The verify token should match what you set in Meta dashboard
    # For simplicity, we accept any verify request
    if hub_mode == "subscribe" and hub_challenge:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp")
async def receive_whatsapp_message(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive incoming WhatsApp messages from Meta Cloud API."""
    payload = await request.json()

    # Parse the incoming message
    incoming = wa_adapter.normalize(payload)
    if not incoming:
        return {"status": "ok"}  # Acknowledge but ignore (status updates, etc.)

    phone_number_id = incoming.metadata.get("phone_number_id", "")

    # Find restaurant by WhatsApp phone number ID
    result = await db.execute(select(Restaurant).where(Restaurant.is_active == True))
    restaurants = result.scalars().all()

    restaurant = None
    config = None
    for r in restaurants:
        rc = RestaurantConfig.model_validate(r.config or {})
        if rc.channels.whatsapp_enabled and rc.channels.whatsapp_phone_number_id == phone_number_id:
            restaurant = r
            config = rc
            break

    if not restaurant:
        return {"status": "ok"}  # No restaurant mapped to this number

    # Check plan — WhatsApp only for paid plans
    if restaurant.plan == "free":
        # Send a message telling them WhatsApp is not available on free plan
        msg = wa_adapter.render(OutgoingMessage(
            recipient_id=incoming.sender_id,
            text="WhatsApp ordering is not available for this restaurant yet. Please visit our website to chat with us!",
        ))
        await wa_adapter.send(phone_number_id, config.channels.whatsapp_access_token or "", msg)
        return {"status": "ok"}

    restaurant_id = restaurant.id

    # Get or create session (keyed by phone number)
    session_key = f"wa-{incoming.sender_id}-{restaurant_id}"
    session = await wa_session_store.get(session_key)
    if not session:
        session = ConversationSession(
            session_id=session_key,
            restaurant_id=restaurant_id,
            channel="whatsapp",
            sender_id=incoming.sender_id,
        )

    # Check auto-replies + FAQs first (FREE)
    auto_response = await check_auto_reply(
        db, restaurant_id, incoming.text, restaurant.name, config
    )

    if auto_response:
        reply_text = auto_response
    else:
        # Use AI agent (PAID)
        deps = RestaurantBotDeps(
            db=db,
            restaurant_id=restaurant_id,
            restaurant_name=restaurant.name,
            config=config,
            session=session,
        )
        try:
            reply_text = await chat_with_agent(deps, incoming.text)
        except Exception:
            reply_text = config.ai.fallback_message

    # Save session
    session.add_message("user", incoming.text)
    session.add_message("assistant", reply_text)
    await wa_session_store.save(session)

    # Log conversation
    try:
        db.add(ConversationLog(
            restaurant_id=restaurant_id,
            session_id=session_key,
            channel="whatsapp",
            role="user",
            content=incoming.text,
        ))
        db.add(ConversationLog(
            restaurant_id=restaurant_id,
            session_id=session_key,
            channel="whatsapp",
            role="assistant",
            content=reply_text,
        ))
    except Exception:
        pass

    # Send reply via WhatsApp
    rendered = wa_adapter.render(OutgoingMessage(
        recipient_id=incoming.sender_id,
        text=reply_text,
    ))
    access_token = config.channels.whatsapp_access_token or ""
    if access_token:
        await wa_adapter.send(phone_number_id, access_token, rendered)

    return {"status": "ok"}


# ─── Telegram Webhooks ────────────────────────────────────────────────────────

@router.post("/telegram/{restaurant_id}")
async def receive_telegram_message(
    restaurant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive incoming Telegram updates for a specific restaurant."""
    payload = await request.json()

    # Parse the incoming update
    incoming = tg_adapter.normalize(payload)
    if not incoming:
        return {"status": "ok"}  # Status updates, stickers, etc.

    # Load restaurant
    result = await db.execute(
        select(Restaurant).where(Restaurant.id == restaurant_id, Restaurant.is_active == True)
    )
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        return {"status": "ok"}

    config = RestaurantConfig.model_validate(restaurant.config or {})

    # Check Telegram is enabled for this restaurant
    if not config.channels.telegram_enabled or not config.channels.telegram_bot_token:
        return {"status": "ok"}

    bot_token = config.channels.telegram_bot_token

    # Acknowledge callback query immediately (dismisses Telegram loading indicator)
    callback_query_id = incoming.metadata.get("callback_query_id", "")
    if callback_query_id:
        await tg_adapter.answer_callback(bot_token, callback_query_id)

    # Get or create session (keyed by Telegram chat_id + restaurant)
    session_key = f"tg-{incoming.sender_id}-{restaurant_id}"
    session = await tg_session_store.get(session_key)
    if not session:
        session = ConversationSession(
            session_id=session_key,
            restaurant_id=str(restaurant_id),
            channel="telegram",
            sender_id=incoming.sender_id,
        )

    # Auto-replies + FAQs first (FREE — no LLM cost)
    auto_response = await check_auto_reply(
        db, restaurant_id, incoming.text, restaurant.name, config
    )

    if auto_response:
        reply_text = auto_response
    else:
        # Use AI agent
        deps = RestaurantBotDeps(
            db=db,
            restaurant_id=str(restaurant_id),
            restaurant_name=restaurant.name,
            config=config,
            session=session,
        )
        try:
            reply_text = await chat_with_agent(deps, incoming.text)
        except Exception:
            reply_text = config.ai.fallback_message

    # Save session
    session.add_message("user", incoming.text)
    session.add_message("assistant", reply_text)
    await tg_session_store.save(session)

    # Log conversation
    try:
        db.add(ConversationLog(
            restaurant_id=restaurant_id,
            session_id=session_key,
            channel="telegram",
            role="user",
            content=incoming.text,
        ))
        db.add(ConversationLog(
            restaurant_id=restaurant_id,
            session_id=session_key,
            channel="telegram",
            role="assistant",
            content=reply_text,
        ))
    except Exception:
        pass

    # Send reply to Telegram
    rendered = tg_adapter.render(OutgoingMessage(
        recipient_id=incoming.sender_id,
        text=reply_text,
    ))
    await tg_adapter.send(bot_token, incoming.sender_id, rendered)

    return {"status": "ok"}


@router.post("/telegram/{restaurant_id}/setup")
async def setup_telegram_webhook(
    restaurant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    """Register this server as the Telegram webhook for a restaurant's bot."""
    result = await db.execute(
        select(Restaurant).where(Restaurant.id == restaurant_id, Restaurant.is_active == True)
    )
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    config = RestaurantConfig.model_validate(restaurant.config or {})
    bot_token = config.channels.telegram_bot_token
    if not bot_token:
        raise HTTPException(
            status_code=400,
            detail="No bot token configured. Save your Telegram Bot Token first."
        )

    # Build the webhook URL from the incoming request's base URL
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/v1/webhooks/telegram/{restaurant_id}"

    # Register webhook with Telegram
    result_data = await tg_adapter.set_webhook(bot_token, webhook_url)
    if not result_data.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=f"Telegram rejected the webhook: {result_data.get('description', 'Unknown error')}"
        )

    # Fetch bot info to return the username
    bot_info = await tg_adapter.get_me(bot_token)
    bot_username = bot_info.get("username", "") if bot_info else ""

    return {
        "ok": True,
        "webhook_url": webhook_url,
        "bot_username": bot_username,
        "message": f"Webhook registered! Your bot @{bot_username} is now connected.",
    }
