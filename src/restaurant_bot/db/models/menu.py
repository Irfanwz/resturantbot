import uuid
from sqlalchemy import String, Boolean, Integer, Text, JSON, ForeignKey, Uuid, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal
from restaurant_bot.db.base import Base, TimestampMixin, TenantMixin

class MenuCategory(Base, TimestampMixin, TenantMixin):
    __tablename__ = "menu_categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    items: Mapped[list["MenuItem"]] = relationship(back_populates="category")

class MenuItem(Base, TimestampMixin, TenantMixin):
    __tablename__ = "menu_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menu_categories.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_vegetarian: Mapped[bool] = mapped_column(Boolean, default=False)
    is_vegan: Mapped[bool] = mapped_column(Boolean, default=False)
    allergens: Mapped[dict] = mapped_column(JSON, default=list)  # ["nuts", "dairy"]
    preparation_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    category: Mapped["MenuCategory"] = relationship(back_populates="items")
    modifiers: Mapped[list["MenuItemModifier"]] = relationship(back_populates="menu_item")

class MenuItemModifier(Base, TenantMixin):
    __tablename__ = "menu_item_modifiers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    menu_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menu_items.id"))
    name: Mapped[str] = mapped_column(String(255))  # "Size", "Extra Toppings"
    options: Mapped[dict] = mapped_column(JSON, default=list)  # [{"name": "Large", "price_delta": 2.00}]
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    max_selections: Mapped[int] = mapped_column(Integer, default=1)

    menu_item: Mapped["MenuItem"] = relationship(back_populates="modifiers")
