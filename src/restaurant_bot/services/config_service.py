import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.models.restaurant import Restaurant
from restaurant_bot.schemas.config import RestaurantConfig


class ConfigService:
    """Loads and caches restaurant configurations."""

    def __init__(self, cache_ttl_seconds: int = 300):
        self._cache: dict[uuid.UUID, tuple[RestaurantConfig, datetime]] = {}
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)

    async def get_config(self, db: AsyncSession, restaurant_id: uuid.UUID) -> RestaurantConfig:
        # Check cache first
        if restaurant_id in self._cache:
            config, cached_at = self._cache[restaurant_id]
            if datetime.now(timezone.utc) - cached_at < self._cache_ttl:
                return config

        # Load from DB
        result = await db.execute(
            select(Restaurant.config).where(Restaurant.id == restaurant_id)
        )
        config_data = result.scalar_one_or_none()
        if config_data is None:
            raise ValueError(f"Restaurant {restaurant_id} not found")

        config = RestaurantConfig.model_validate(config_data or {})
        self._cache[restaurant_id] = (config, datetime.now(timezone.utc))
        return config

    async def update_config(
        self, db: AsyncSession, restaurant_id: uuid.UUID, config: RestaurantConfig
    ) -> RestaurantConfig:
        config_dict = config.model_dump(mode="json")
        await db.execute(
            update(Restaurant)
            .where(Restaurant.id == restaurant_id)
            .values(config=config_dict)
        )
        await db.flush()
        # Invalidate cache
        self._cache.pop(restaurant_id, None)
        return config

    async def update_config_section(
        self, db: AsyncSession, restaurant_id: uuid.UUID, section: str, data: dict
    ) -> RestaurantConfig:
        current = await self.get_config(db, restaurant_id)
        section_model = getattr(current, section, None)
        if section_model is None:
            raise ValueError(f"Unknown config section: {section}")

        updated_section = section_model.model_copy(update=data)
        updated_config = current.model_copy(update={section: updated_section})
        return await self.update_config(db, restaurant_id, updated_config)

    def invalidate(self, restaurant_id: uuid.UUID) -> None:
        self._cache.pop(restaurant_id, None)

    def invalidate_all(self) -> None:
        self._cache.clear()


# Global singleton
config_service = ConfigService()
