import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Boolean, Integer, Text, JSON, ForeignKey, Uuid, Numeric, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from restaurant_bot.db.base import Base, TimestampMixin, TenantMixin

class Customer(Base, TimestampMixin, TenantMixin):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "channel", "channel_user_id", name="uq_customer_channel"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    channel: Mapped[str] = mapped_column(String(50))  # "rest_api", "whatsapp", "telegram"
    channel_user_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

class Order(Base, TimestampMixin, TenantMixin):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"))
    order_number: Mapped[str] = mapped_column(String(50), index=True)  # "ORD-0042"
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, confirmed, preparing, ready, delivered, cancelled
    order_type: Mapped[str] = mapped_column(String(20), default="dine_in")  # dine_in, takeaway, delivery
    table_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    tax: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str] = mapped_column(String(50))
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    estimated_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("orders.id"))
    menu_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menu_items.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    modifiers: Mapped[dict] = mapped_column(JSON, default=list)  # snapshot of selected modifiers
    item_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="items")
