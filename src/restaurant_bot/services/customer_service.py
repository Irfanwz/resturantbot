import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from restaurant_bot.db.models.order import Customer


async def get_customer_by_channel(
    db: AsyncSession,
    restaurant_id: uuid.UUID,
    channel: str,
    channel_user_id: str,
) -> Customer | None:
    result = await db.execute(
        select(Customer).where(
            Customer.restaurant_id == restaurant_id,
            Customer.channel == channel,
            Customer.channel_user_id == channel_user_id,
        )
    )
    return result.scalar_one_or_none()
