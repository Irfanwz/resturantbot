import uuid
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.models.conversation import AutoReply
from restaurant_bot.schemas.config import RestaurantConfig


async def get_auto_replies(db: AsyncSession, restaurant_id: uuid.UUID) -> list[AutoReply]:
    """Get all active auto-replies for a restaurant, sorted by priority (highest first)."""
    result = await db.execute(
        select(AutoReply)
        .where(AutoReply.restaurant_id == restaurant_id, AutoReply.is_active == True)
        .order_by(AutoReply.priority.desc())
    )
    return list(result.scalars().all())


def match_auto_reply(
    message: str,
    auto_replies: list[AutoReply],
) -> AutoReply | None:
    """Check if a message matches any auto-reply pattern. Returns the first match or None."""
    message_lower = message.lower().strip()
    # Remove punctuation for matching
    message_clean = re.sub(r'[^\w\s]', '', message_lower)
    message_words = set(message_clean.split())

    for reply in auto_replies:
        patterns = reply.trigger_patterns
        if not isinstance(patterns, list):
            continue

        if reply.match_type == "exact":
            # Exact match: full message must match one of the patterns
            for pattern in patterns:
                if message_clean == pattern.lower().strip():
                    return reply
                # Also check with punctuation
                if message_lower == pattern.lower().strip():
                    return reply
        else:
            # Keyword match: any trigger word found in the message
            for pattern in patterns:
                pattern_lower = pattern.lower().strip()
                # For short patterns (1-2 words), check if the message is basically just that
                pattern_words = pattern_lower.split()
                if len(pattern_words) == 1 and len(message_words) <= 3:
                    if pattern_lower in message_words:
                        return reply
                elif len(pattern_words) > 1:
                    # Multi-word pattern: check if all words are present
                    if all(w in message_words for w in pattern_words):
                        return reply

    return None


def render_response(
    template: str,
    restaurant_name: str,
    config: RestaurantConfig,
) -> str:
    """Render a response template with variables."""
    variables = {
        "restaurant_name": restaurant_name,
        "greeting_message": config.ai.greeting_message,
        "farewell_message": config.ai.farewell_message,
        "bot_name": config.ai.bot_name,
        "address": config.business.address or "Address not set",
        "phone": config.business.phone or "Phone not set",
        "email": config.business.email or "Email not set",
        "cuisine": ", ".join(config.business.cuisine_type) if config.business.cuisine_type else "Various",
        "price_range": config.business.price_range,
    }

    result = template
    for key, value in variables.items():
        result = result.replace("{" + key + "}", value)
    return result


async def check_faq_match(
    db: AsyncSession,
    restaurant_id: uuid.UUID,
    message: str,
    restaurant_name: str,
    config: RestaurantConfig,
) -> str | None:
    """Check if a message matches any FAQ. Returns the answer if matched, None otherwise."""
    from restaurant_bot.db.models.conversation import FAQ

    result = await db.execute(
        select(FAQ).where(
            FAQ.restaurant_id == restaurant_id,
            FAQ.is_active == True,
        ).order_by(FAQ.sort_order)
    )
    faqs = list(result.scalars().all())

    if not faqs:
        return None

    message_lower = message.lower().strip()
    message_clean = re.sub(r'[^\w\s]', '', message_lower)
    message_words = set(message_clean.split())

    best_match = None
    best_score = 0

    for faq in faqs:
        question_lower = faq.question.lower()
        question_clean = re.sub(r'[^\w\s]', '', question_lower)
        question_words = set(question_clean.split())

        # Remove common stop words for better matching
        stop_words = {'do', 'you', 'have', 'is', 'are', 'the', 'a', 'an', 'what', 'how', 'can', 'i', 'we', 'my', 'your', 'does', 'it', 'this', 'that', 'there', 'any'}
        msg_significant = message_words - stop_words
        q_significant = question_words - stop_words

        if not msg_significant or not q_significant:
            continue

        # Calculate word overlap score
        overlap = msg_significant & q_significant
        if overlap:
            score = len(overlap) / max(len(msg_significant), len(q_significant))
            # Boost score if most of the question's key words are present
            coverage = len(overlap) / len(q_significant)
            score = (score + coverage) / 2

            if score > best_score and score >= 0.4:  # 40% minimum match threshold
                best_score = score
                best_match = faq

    if best_match:
        answer = render_response(best_match.answer, restaurant_name, config)
        return answer

    return None


async def check_auto_reply(
    db: AsyncSession,
    restaurant_id: uuid.UUID,
    message: str,
    restaurant_name: str,
    config: RestaurantConfig,
) -> str | None:
    """
    Check if a message matches any auto-reply or FAQ.
    Returns the rendered response if matched, None if should fall through to LLM.

    Priority: Auto-replies first (exact patterns), then FAQs (fuzzy match).
    """
    # 1. Check auto-replies first (pattern-based, fast)
    auto_replies = await get_auto_replies(db, restaurant_id)
    matched = match_auto_reply(message, auto_replies)

    if matched:
        return render_response(matched.response, restaurant_name, config)

    # 2. Check FAQs (fuzzy word matching, still free)
    faq_response = await check_faq_match(db, restaurant_id, message, restaurant_name, config)
    if faq_response:
        return faq_response

    return None


# --- CRUD operations for admin API ---

async def create_auto_reply(
    db: AsyncSession,
    restaurant_id: uuid.UUID,
    trigger_patterns: list[str],
    response: str,
    category: str = "custom",
    priority: int = 0,
    match_type: str = "keyword",
) -> AutoReply:
    auto_reply = AutoReply(
        restaurant_id=restaurant_id,
        trigger_patterns=trigger_patterns,
        response=response,
        category=category,
        priority=priority,
        match_type=match_type,
    )
    db.add(auto_reply)
    await db.flush()
    return auto_reply


async def get_auto_reply(db: AsyncSession, restaurant_id: uuid.UUID, reply_id: uuid.UUID) -> AutoReply | None:
    result = await db.execute(
        select(AutoReply).where(
            AutoReply.id == reply_id,
            AutoReply.restaurant_id == restaurant_id,
        )
    )
    return result.scalar_one_or_none()


async def update_auto_reply(db: AsyncSession, auto_reply: AutoReply, **kwargs) -> AutoReply:
    for key, value in kwargs.items():
        if value is not None:
            setattr(auto_reply, key, value)
    await db.flush()
    return auto_reply


async def delete_auto_reply(db: AsyncSession, auto_reply: AutoReply) -> None:
    await db.delete(auto_reply)
    await db.flush()
