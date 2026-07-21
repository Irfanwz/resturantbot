import uuid
from datetime import date, time, datetime, timezone
from pydantic_ai import RunContext

from restaurant_bot.agent.deps import RestaurantBotDeps
from restaurant_bot.services.reservation_service import (
    check_availability,
    create_reservation,
)
from restaurant_bot.services.order_service import get_or_create_customer


async def check_table_availability(
    ctx: RunContext[RestaurantBotDeps],
    reservation_date: str,
    reservation_time: str,
    party_size: int,
) -> str:
    """Check if tables are available for a given date, time, and party size. Date format: YYYY-MM-DD. Time format: HH:MM."""
    config = ctx.deps.config
    if not config.reservations.reservations_enabled:
        return "Table reservations are not available at this restaurant."

    if party_size > config.reservations.max_party_size:
        return f"Sorry, maximum party size is {config.reservations.max_party_size}. For larger groups, please contact the restaurant directly."

    try:
        res_date = date.fromisoformat(reservation_date)
        res_time = time.fromisoformat(reservation_time)
    except ValueError:
        return "Invalid date or time format. Please use YYYY-MM-DD for date and HH:MM for time."

    available_tables = await check_availability(
        ctx.deps.db,
        ctx.deps.restaurant_id,
        res_date,
        res_time,
        party_size,
        config.reservations.default_duration_minutes,
    )

    if available_tables:
        return f"Great news! We have {len(available_tables)} table(s) available on {reservation_date} at {reservation_time} for {party_size} guests. Would you like to make a reservation?"
    else:
        # Suggest alternative slots
        from restaurant_bot.services.reservation_service import get_available_slots
        slots = await get_available_slots(
            ctx.deps.db,
            ctx.deps.restaurant_id,
            res_date,
            party_size,
            config.reservations.default_duration_minutes,
            config.reservations.time_slot_interval_minutes,
        )
        if slots:
            slot_list = ", ".join(slots[:6])
            return f"Sorry, no tables available for {party_size} guests on {reservation_date} at {reservation_time}.\n\nAvailable times that day: {slot_list}\n\nWould you like to book one of these instead?"
        else:
            return f"Sorry, no tables available for {party_size} guests on {reservation_date}. Would you like to try a different date?"


async def make_reservation(
    ctx: RunContext[RestaurantBotDeps],
    reservation_date: str,
    reservation_time: str,
    party_size: int,
    customer_name: str | None = None,
    special_requests: str | None = None,
) -> str:
    """Make a table reservation. Date format: YYYY-MM-DD. Time format: HH:MM. Always check availability first."""
    config = ctx.deps.config
    db = ctx.deps.db
    session = ctx.deps.session

    if not config.reservations.reservations_enabled:
        return "Reservations are not available at this restaurant."

    try:
        res_date = date.fromisoformat(reservation_date)
        res_time = time.fromisoformat(reservation_time)
    except ValueError:
        return "Invalid date or time format."

    # Check availability
    available_tables = await check_availability(
        db, ctx.deps.restaurant_id, res_date, res_time, party_size,
        config.reservations.default_duration_minutes,
    )
    if not available_tables:
        return f"Sorry, no tables available for {party_size} on {reservation_date} at {reservation_time}."

    customer = await get_or_create_customer(
        db, ctx.deps.restaurant_id, session.channel, session.sender_id, name=customer_name
    )

    table = available_tables[0]
    reservation = await create_reservation(
        db=db,
        restaurant_id=ctx.deps.restaurant_id,
        customer_id=customer.id,
        party_size=party_size,
        reservation_date=res_date,
        reservation_time=res_time,
        channel=session.channel,
        duration_minutes=config.reservations.default_duration_minutes,
        table_id=table.id,
        special_requests=special_requests,
    )

    status = "confirmed" if config.reservations.auto_confirm_reservations else "pending confirmation"
    return f"""Reservation {status}!

- Date: {reservation_date}
- Time: {reservation_time}
- Party size: {party_size}
- Table: {table.table_number}
- Duration: {config.reservations.default_duration_minutes} minutes
{f'- Special requests: {special_requests}' if special_requests else ''}

{config.reservations.cancellation_policy}"""


async def cancel_reservation(ctx: RunContext[RestaurantBotDeps], reservation_id: str) -> str:
    """Cancel an existing reservation by ID."""
    from restaurant_bot.services.reservation_service import get_reservation, update_reservation_status

    try:
        res_uuid = uuid.UUID(reservation_id)
    except ValueError:
        return "Invalid reservation ID."

    reservation = await get_reservation(ctx.deps.db, ctx.deps.restaurant_id, res_uuid)
    if not reservation:
        return "Reservation not found."

    if reservation.status in ("cancelled", "completed", "no_show"):
        return f"This reservation is already {reservation.status}."

    await update_reservation_status(ctx.deps.db, reservation, "cancelled")
    return "Your reservation has been cancelled successfully."
