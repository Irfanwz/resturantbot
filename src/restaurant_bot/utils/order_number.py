import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from restaurant_bot.db.models.order import Order


async def generate_order_number(db: AsyncSession, restaurant_id: uuid.UUID, prefix: str = "ORD") -> str:
    result = await db.execute(
        select(func.count(Order.id)).where(Order.restaurant_id == restaurant_id)
    )
    count = result.scalar() or 0
    return f"{prefix}-{count + 1:04d}"
