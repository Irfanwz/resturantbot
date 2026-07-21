import uuid
from pydantic import BaseModel, Field
from restaurant_bot.schemas.config import RestaurantConfig


class RestaurantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = None  # auto-generated from name if not provided
    timezone: str = "UTC"
    currency: str = "USD"


class RestaurantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    currency: str
    is_active: bool
    config: RestaurantConfig

    model_config = {"from_attributes": True}


class RestaurantUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None
    currency: str | None = None
    is_active: bool | None = None
