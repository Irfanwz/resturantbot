import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from restaurant_bot.db.models.order import Order, OrderItem, Customer
from restaurant_bot.session.cart import Cart


async def get_or_create_customer(
    db: AsyncSession,
    restaurant_id: uuid.UUID,
    channel: str,
    channel_user_id: str,
    name: str | None = None,
    phone: str | None = None,
) -> Customer:
    result = await db.execute(
        select(Customer).where(
            Customer.restaurant_id == restaurant_id,
            Customer.channel == channel,
            Customer.channel_user_id == channel_user_id,
        )
    )
    customer = result.scalar_one_or_none()
    if customer:
        if name and not customer.name:
            customer.name = name
        if phone and not customer.phone:
            customer.phone = phone
        await db.flush()
        return customer

    customer = Customer(
        restaurant_id=restaurant_id,
        channel=channel,
        channel_user_id=channel_user_id,
        name=name,
        phone=phone,
    )
    db.add(customer)
    await db.flush()
    return customer


async def generate_order_number(db: AsyncSession, restaurant_id: uuid.UUID, prefix: str = "ORD") -> str:
    result = await db.execute(
        select(func.count(Order.id)).where(Order.restaurant_id == restaurant_id)
    )
    count = result.scalar() or 0
    return f"{prefix}-{count + 1:04d}"


async def place_order(
    db: AsyncSession,
    restaurant_id: uuid.UUID,
    customer_id: uuid.UUID,
    cart: Cart,
    order_type: str = "dine_in",
    channel: str = "rest_api",
    table_number: str | None = None,
    special_instructions: str | None = None,
    tax_rate: Decimal = Decimal("0.00"),
    order_number_prefix: str = "ORD",
    delivery_address: str | None = None,
    delivery_fee: Decimal = Decimal("0.00"),
    preparation_buffer_minutes: int = 15,
) -> Order:
    order_number = await generate_order_number(db, restaurant_id, order_number_prefix)
    subtotal = cart.subtotal
    tax = subtotal * tax_rate
    total = subtotal + tax + delivery_fee

    estimated_ready_at = datetime.now(timezone.utc) + timedelta(minutes=preparation_buffer_minutes)

    # Prepend delivery address to special instructions if provided
    if delivery_address:
        address_prefix = f"Delivery to: {delivery_address}"
        if special_instructions:
            special_instructions = f"{address_prefix}\n{special_instructions}"
        else:
            special_instructions = address_prefix

    order = Order(
        restaurant_id=restaurant_id,
        customer_id=customer_id,
        order_number=order_number,
        status="pending",
        order_type=order_type,
        table_number=table_number,
        subtotal=subtotal,
        tax=tax,
        total=total,
        special_instructions=special_instructions,
        channel=channel,
    )
    order.estimated_ready_at = estimated_ready_at
    db.add(order)
    await db.flush()

    for cart_item in cart.items:
        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=cart_item.menu_item_id,
            quantity=cart_item.quantity,
            unit_price=cart_item.unit_price,
            modifiers=cart_item.modifiers,
            item_total=cart_item.item_total,
            special_instructions=cart_item.special_instructions,
        )
        db.add(order_item)

    await db.flush()
    return order


async def get_order(db: AsyncSession, restaurant_id: uuid.UUID, order_id: uuid.UUID) -> Order | None:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.restaurant_id == restaurant_id)
        .options(selectinload(Order.items))
    )
    return result.scalar_one_or_none()


async def get_order_by_number(db: AsyncSession, restaurant_id: uuid.UUID, order_number: str) -> Order | None:
    result = await db.execute(
        select(Order)
        .where(Order.order_number == order_number, Order.restaurant_id == restaurant_id)
        .options(selectinload(Order.items))
    )
    return result.scalar_one_or_none()


async def get_customer_orders(db: AsyncSession, restaurant_id: uuid.UUID, customer_id: uuid.UUID) -> list[Order]:
    result = await db.execute(
        select(Order)
        .where(Order.restaurant_id == restaurant_id, Order.customer_id == customer_id)
        .options(selectinload(Order.items))
        .order_by(Order.placed_at.desc())
        .limit(10)
    )
    return list(result.scalars().all())


async def update_order_status(db: AsyncSession, order: Order, status: str) -> Order:
    order.status = status
    if status in ("delivered", "completed"):
        order.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return order
