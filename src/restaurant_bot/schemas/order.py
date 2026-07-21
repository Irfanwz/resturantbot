import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class CartItem(BaseModel):
    menu_item_id: uuid.UUID
    name: str
    quantity: int = 1
    unit_price: Decimal
    modifiers: list[dict] = Field(default_factory=list)
    special_instructions: str | None = None
    item_total: Decimal


class CartSummary(BaseModel):
    items: list[CartItem] = Field(default_factory=list)
    subtotal: Decimal = Decimal("0.00")
    tax: Decimal = Decimal("0.00")
    delivery_fee: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    item_count: int = 0


class AddToCartRequest(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=99)
    modifiers: list[dict] = Field(default_factory=list)
    special_instructions: str | None = None


class PlaceOrderRequest(BaseModel):
    order_type: str = "dine_in"  # dine_in, takeaway, delivery
    table_number: str | None = None
    special_instructions: str | None = None
    delivery_address: str | None = None


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    menu_item_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    modifiers: list[dict]
    item_total: Decimal
    special_instructions: str | None

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    status: str
    order_type: str
    table_number: str | None
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    special_instructions: str | None
    channel: str
    placed_at: datetime
    estimated_ready_at: datetime | None
    items: list[OrderItemResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: str  # confirmed, preparing, ready, delivered, cancelled
