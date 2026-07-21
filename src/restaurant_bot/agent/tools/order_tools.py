import uuid
from decimal import Decimal
from pydantic_ai import RunContext
from sqlalchemy import select

from restaurant_bot.agent.deps import RestaurantBotDeps
from restaurant_bot.db.models.menu import MenuItem
from restaurant_bot.session.cart import CartItem
from restaurant_bot.services.order_service import (
    get_or_create_customer,
    place_order as place_order_service,
    get_order_by_number,
    get_customer_orders,
)


async def add_to_cart(ctx: RunContext[RestaurantBotDeps], item_name: str, quantity: int = 1, modifiers: list[dict] | None = None, special_instructions: str | None = None) -> str:
    """Add an item to the customer's cart. Use this when a customer wants to order something. Always search/confirm the item name first."""
    db = ctx.deps.db
    session = ctx.deps.session
    config = ctx.deps.config

    if not config.ordering.ordering_enabled:
        return "Ordering is currently disabled for this restaurant."

    # Find the item
    result = await db.execute(
        select(MenuItem).where(
            MenuItem.restaurant_id == ctx.deps.restaurant_id,
            MenuItem.is_available == True,
            MenuItem.name.ilike(f"%{item_name}%"),
        )
    )
    item = result.scalars().first()
    if not item:
        return f"Sorry, I couldn't find '{item_name}' on the menu. Please check the menu and try again."

    if session.cart.item_count + quantity > config.ordering.max_items_per_order:
        return f"Sorry, maximum {config.ordering.max_items_per_order} items per order."

    cart_item = CartItem(
        menu_item_id=item.id,
        name=item.name,
        quantity=quantity,
        unit_price=item.price,
        modifiers=modifiers if modifiers else [],
        special_instructions=special_instructions,
    )
    session.cart.add_item(cart_item)

    cart_summary = f"Added {quantity}x {item.name} ({item.price} each) to your cart.\n\n"
    cart_summary += f"Cart total: {session.cart.subtotal} ({session.cart.item_count} items)"
    return cart_summary


async def remove_from_cart(ctx: RunContext[RestaurantBotDeps], item_name: str) -> str:
    """Remove an item from the customer's cart."""
    session = ctx.deps.session

    for cart_item in session.cart.items:
        if item_name.lower() in cart_item.name.lower():
            session.cart.remove_item(cart_item.menu_item_id)
            return f"Removed {cart_item.name} from your cart.\n\nCart total: {session.cart.subtotal} ({session.cart.item_count} items)"

    return f"'{item_name}' is not in your cart."


async def get_cart(ctx: RunContext[RestaurantBotDeps]) -> str:
    """Show the current cart contents and total. Use this when a customer wants to review their order before placing it."""
    session = ctx.deps.session
    config = ctx.deps.config

    if session.cart.is_empty:
        return "Your cart is empty. Would you like to see the menu?"

    lines = ["Here's what's in your cart:\n"]
    for item in session.cart.items:
        lines.append(f"- {item.quantity}x {item.name} — {item.item_total}")

    subtotal = session.cart.subtotal
    lines.append(f"\nSubtotal: {subtotal}")

    if config.ordering.tax_rate > 0 and not config.ordering.tax_inclusive:
        tax = subtotal * config.ordering.tax_rate
        lines.append(f"Tax ({float(config.ordering.tax_rate) * 100}%): {tax}")
        lines.append(f"Total: {subtotal + tax}")

    return "\n".join(lines)


async def place_order(ctx: RunContext[RestaurantBotDeps], order_type: str = "dine_in", table_number: str | None = None) -> str:
    """Place the order with items currently in the cart. Call this when the customer confirms they want to place their order. order_type can be 'dine_in', 'takeaway', or 'delivery'."""
    db = ctx.deps.db
    session = ctx.deps.session
    config = ctx.deps.config

    if session.cart.is_empty:
        return "Your cart is empty. Please add items before placing an order."

    if not config.ordering.ordering_enabled:
        return "Ordering is currently disabled."

    if order_type not in config.ordering.order_types and not (order_type == "delivery" and config.ordering.delivery_enabled):
        available = ", ".join(config.ordering.order_types)
        return f"Sorry, '{order_type}' is not available. Available options: {available}"

    if config.ordering.minimum_order_amount > 0 and session.cart.subtotal < config.ordering.minimum_order_amount:
        return f"Minimum order amount is {config.ordering.minimum_order_amount}. Your cart total is {session.cart.subtotal}."

    customer = await get_or_create_customer(
        db, ctx.deps.restaurant_id, session.channel, session.sender_id
    )

    delivery_fee = config.ordering.delivery_fee if order_type == "delivery" else Decimal("0.00")

    order = await place_order_service(
        db=db,
        restaurant_id=ctx.deps.restaurant_id,
        customer_id=customer.id,
        cart=session.cart,
        order_type=order_type,
        channel=session.channel,
        table_number=table_number,
        tax_rate=config.ordering.tax_rate,
        order_number_prefix=config.ordering.order_number_prefix,
        delivery_fee=delivery_fee,
        preparation_buffer_minutes=config.ordering.preparation_buffer_minutes,
    )

    # Snapshot cart items before clearing (for notifications)
    cart_items_snapshot = list(session.cart.items)
    session.cart.clear()

    # Trigger notifications (non-blocking)
    try:
        items_text = ", ".join(f"{ci.quantity}x {ci.name}" for ci in cart_items_snapshot)
        # Store notification data in session for the chat endpoint to pick up
        session.add_message("system", f"__ORDER_PLACED__|{order.order_number}|{order.total}|{order_type}|{items_text}")
    except Exception:
        pass

    status_msg = "Your order has been confirmed!" if config.ordering.auto_confirm_orders else "Your order has been placed and is awaiting confirmation."
    est_time = f"\nEstimated ready: ~{config.ordering.preparation_buffer_minutes} minutes" if order.estimated_ready_at else ""
    return f"{status_msg}\n\nOrder number: **{order.order_number}**\nTotal: {order.total}\nType: {order_type}{est_time}\n\nYou can ask me about your order status anytime using your order number."


async def get_order_status(ctx: RunContext[RestaurantBotDeps], order_number: str) -> str:
    """Check the status of an order by order number. Use when a customer asks about their order."""
    db = ctx.deps.db
    order = await get_order_by_number(db, ctx.deps.restaurant_id, order_number)

    if not order:
        return f"I couldn't find order {order_number}. Please check the order number and try again."

    status_display = {
        "pending": "Pending — waiting for restaurant confirmation",
        "confirmed": "Confirmed — the restaurant is preparing your order",
        "preparing": "Being prepared in the kitchen",
        "ready": "Ready for pickup/serving!",
        "delivered": "Delivered",
        "cancelled": "Cancelled",
    }

    lines = [
        f"Order **{order.order_number}**:",
        f"- Status: {status_display.get(order.status, order.status)}",
        f"- Type: {order.order_type}",
        f"- Total: {order.total}",
        f"- Placed: {order.placed_at.strftime('%H:%M')}",
    ]
    if order.estimated_ready_at:
        lines.append(f"- Estimated ready: {order.estimated_ready_at.strftime('%H:%M')}")

    return "\n".join(lines)


async def update_cart_quantity(ctx: RunContext[RestaurantBotDeps], item_name: str, quantity: int) -> str:
    """Update the quantity of an item in the cart. Set quantity to 0 to remove it."""
    session = ctx.deps.session

    for cart_item in session.cart.items:
        if item_name.lower() in cart_item.name.lower():
            if quantity <= 0:
                session.cart.remove_item(cart_item.menu_item_id)
                return f"Removed {cart_item.name} from your cart.\n\nCart total: {session.cart.subtotal} ({session.cart.item_count} items)"
            old_qty = cart_item.quantity
            session.cart.update_quantity(cart_item.menu_item_id, quantity)
            return f"Updated {cart_item.name}: {old_qty} → {quantity}\n\nCart total: {session.cart.subtotal} ({session.cart.item_count} items)"

    return f"'{item_name}' is not in your cart."


async def get_my_orders(ctx: RunContext[RestaurantBotDeps]) -> str:
    """Get the customer's recent order history. Use when a customer asks about their past orders."""
    db = ctx.deps.db
    session = ctx.deps.session

    customer = await get_or_create_customer(
        db, ctx.deps.restaurant_id, session.channel, session.sender_id
    )

    orders = await get_customer_orders(db, ctx.deps.restaurant_id, customer.id)

    if not orders:
        return "You don't have any previous orders yet."

    lines = [f"Your recent orders ({len(orders)}):\n"]
    for order in orders:
        items_summary = ", ".join(
            f"{oi.quantity}x {oi.menu_item_id}" for oi in order.items[:3]
        )
        if len(order.items) > 3:
            items_summary += f" +{len(order.items) - 3} more"
        lines.append(
            f"- **{order.order_number}** | {order.status} | {order.total} | {order.placed_at.strftime('%b %d, %H:%M')}"
        )

    return "\n".join(lines)
