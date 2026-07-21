import uuid
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from restaurant_bot.schemas.config import RestaurantConfig
from restaurant_bot.session.base import ConversationSession


@dataclass
class RestaurantBotDeps:
    db: AsyncSession
    restaurant_id: uuid.UUID
    restaurant_name: str
    config: RestaurantConfig
    session: ConversationSession
