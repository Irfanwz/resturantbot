import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from restaurant_bot.session.base import SessionStore, ConversationSession
from restaurant_bot.session.cart import Cart, CartItem


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def session_to_dict(session: ConversationSession) -> dict:
    return {
        "session_id": session.session_id,
        "restaurant_id": str(session.restaurant_id),
        "customer_id": str(session.customer_id) if session.customer_id else None,
        "channel": session.channel,
        "sender_id": session.sender_id,
        "cart": session.cart.to_dict(),
        "conversation_history": session.conversation_history,
        "created_at": session.created_at.isoformat(),
        "last_active_at": session.last_active_at.isoformat(),
    }


def session_from_dict(data: dict) -> ConversationSession:
    cart = Cart()
    cart_data = data.get("cart", {})
    for item in cart_data.get("items", []):
        cart.add_item(CartItem(
            menu_item_id=uuid.UUID(item["menu_item_id"]),
            name=item["name"],
            quantity=item["quantity"],
            unit_price=Decimal(item["unit_price"]),
            modifiers=item.get("modifiers", []),
            special_instructions=item.get("special_instructions"),
        ))

    return ConversationSession(
        session_id=data["session_id"],
        restaurant_id=uuid.UUID(data["restaurant_id"]),
        customer_id=uuid.UUID(data["customer_id"]) if data.get("customer_id") else None,
        channel=data.get("channel", "rest_api"),
        sender_id=data.get("sender_id", "anonymous"),
        cart=cart,
        conversation_history=data.get("conversation_history", []),
        created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
        last_active_at=datetime.fromisoformat(data["last_active_at"]) if data.get("last_active_at") else datetime.now(timezone.utc),
    )


class RedisSessionStore(SessionStore):
    """Redis-backed session store for production use."""

    def __init__(self, redis_url: str, ttl_minutes: int = 60, prefix: str = "session:"):
        self._redis_url = redis_url
        self._ttl = ttl_minutes * 60  # convert to seconds
        self._prefix = prefix
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    async def get(self, session_id: str) -> ConversationSession | None:
        r = await self._get_redis()
        data = await r.get(self._key(session_id))
        if data is None:
            return None
        return session_from_dict(json.loads(data))

    async def save(self, session: ConversationSession) -> None:
        r = await self._get_redis()
        data = json.dumps(session_to_dict(session), cls=DecimalEncoder)
        await r.setex(self._key(session.session_id), self._ttl, data)

    async def delete(self, session_id: str) -> None:
        r = await self._get_redis()
        await r.delete(self._key(session_id))
