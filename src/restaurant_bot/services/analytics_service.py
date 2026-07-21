import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, case, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession
from restaurant_bot.db.models.order import Order, OrderItem
from restaurant_bot.db.models.conversation import ConversationLog
from restaurant_bot.db.models.reservation import Reservation
from restaurant_bot.db.models.menu import MenuItem


async def get_order_stats(db: AsyncSession, restaurant_id: uuid.UUID) -> dict:
    """Basic order statistics."""
    total = await db.execute(
        select(func.count(Order.id)).where(Order.restaurant_id == restaurant_id)
    )
    revenue = await db.execute(
        select(func.sum(Order.total)).where(
            Order.restaurant_id == restaurant_id,
            Order.status != "cancelled",
        )
    )
    pending = await db.execute(
        select(func.count(Order.id)).where(
            Order.restaurant_id == restaurant_id,
            Order.status == "pending",
        )
    )
    avg_order = await db.execute(
        select(func.avg(Order.total)).where(
            Order.restaurant_id == restaurant_id,
            Order.status != "cancelled",
        )
    )
    return {
        "total_orders": total.scalar() or 0,
        "total_revenue": str(revenue.scalar() or 0),
        "pending_orders": pending.scalar() or 0,
        "average_order_value": str(round(float(avg_order.scalar() or 0), 2)),
    }


async def get_conversation_count(db: AsyncSession, restaurant_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(func.distinct(ConversationLog.session_id))).where(
            ConversationLog.restaurant_id == restaurant_id
        )
    )
    return result.scalar() or 0


async def get_popular_items(db: AsyncSession, restaurant_id: uuid.UUID, limit: int = 10) -> list[dict]:
    """Get most ordered items."""
    result = await db.execute(
        select(
            OrderItem.menu_item_id,
            func.sum(OrderItem.quantity).label("total_qty"),
            func.sum(OrderItem.item_total).label("total_revenue"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.restaurant_id == restaurant_id, Order.status != "cancelled")
        .group_by(OrderItem.menu_item_id)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(limit)
    )
    rows = result.all()

    items = []
    for row in rows:
        item_result = await db.execute(
            select(MenuItem.name).where(MenuItem.id == row.menu_item_id)
        )
        name = item_result.scalar() or "Unknown"
        items.append({
            "name": name,
            "total_ordered": int(row.total_qty),
            "total_revenue": str(row.total_revenue),
        })
    return items


async def get_order_status_breakdown(db: AsyncSession, restaurant_id: uuid.UUID) -> dict:
    """Count orders by status."""
    result = await db.execute(
        select(Order.status, func.count(Order.id))
        .where(Order.restaurant_id == restaurant_id)
        .group_by(Order.status)
    )
    return {row[0]: row[1] for row in result.all()}


async def get_channel_breakdown(db: AsyncSession, restaurant_id: uuid.UUID) -> dict:
    """Count conversations by channel."""
    result = await db.execute(
        select(
            ConversationLog.channel,
            func.count(func.distinct(ConversationLog.session_id)),
        )
        .where(ConversationLog.restaurant_id == restaurant_id)
        .group_by(ConversationLog.channel)
    )
    return {row[0]: row[1] for row in result.all()}


async def get_full_dashboard(db: AsyncSession, restaurant_id: uuid.UUID) -> dict:
    """Get all analytics for the dashboard."""
    order_stats = await get_order_stats(db, restaurant_id)
    conversations = await get_conversation_count(db, restaurant_id)
    popular = await get_popular_items(db, restaurant_id, limit=5)
    status_breakdown = await get_order_status_breakdown(db, restaurant_id)
    channel_breakdown = await get_channel_breakdown(db, restaurant_id)

    return {
        **order_stats,
        "total_conversations": conversations,
        "popular_items": popular,
        "order_status_breakdown": status_breakdown,
        "channel_breakdown": channel_breakdown,
    }
