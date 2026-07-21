import uuid
from decimal import Decimal
from pydantic import BaseModel, Field


class ModifierOption(BaseModel):
    name: str
    price_delta: Decimal = Decimal("0.00")


class MenuItemModifierCreate(BaseModel):
    name: str
    options: list[ModifierOption] = Field(default_factory=list)
    is_required: bool = False
    max_selections: int = 1


class MenuItemModifierResponse(MenuItemModifierCreate):
    id: uuid.UUID

    model_config = {"from_attributes": True}


class MenuItemCreate(BaseModel):
    category_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    price: Decimal = Field(..., ge=0)
    image_url: str | None = None
    is_available: bool = True
    is_vegetarian: bool = False
    is_vegan: bool = False
    allergens: list[str] = Field(default_factory=list)
    preparation_time_minutes: int | None = None
    sort_order: int = 0


class MenuItemUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = None
    description: str | None = None
    price: Decimal | None = None
    image_url: str | None = None
    is_available: bool | None = None
    is_vegetarian: bool | None = None
    is_vegan: bool | None = None
    allergens: list[str] | None = None
    preparation_time_minutes: int | None = None
    sort_order: int | None = None


class MenuItemResponse(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str
    price: Decimal
    image_url: str | None
    is_available: bool
    is_vegetarian: bool
    is_vegan: bool
    allergens: list[str]
    preparation_time_minutes: int | None
    sort_order: int
    modifiers: list[MenuItemModifierResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MenuCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    sort_order: int = 0


class MenuCategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class MenuCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    sort_order: int
    is_active: bool
    items: list[MenuItemResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MenuResponse(BaseModel):
    """Full menu with all categories and items."""
    restaurant_name: str
    currency: str
    categories: list[MenuCategoryResponse]
