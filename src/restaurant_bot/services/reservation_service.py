import uuid
from datetime import date, time, datetime, timedelta, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.models.reservation import Table, Reservation


async def get_tables(db: AsyncSession, restaurant_id: uuid.UUID) -> list[Table]:
    result = await db.execute(
        select(Table).where(Table.restaurant_id == restaurant_id, Table.is_active == True)
    )
    return list(result.scalars().all())


async def check_availability(
    db: AsyncSession,
    restaurant_id: uuid.UUID,
    reservation_date: date,
    reservation_time: time,
    party_size: int,
    duration_minutes: int = 90,
) -> list[Table]:
    # Get all tables that can fit the party
    tables_result = await db.execute(
        select(Table).where(
            Table.restaurant_id == restaurant_id,
            Table.is_active == True,
            Table.capacity >= party_size,
        )
    )
    all_tables = list(tables_result.scalars().all())

    if not all_tables:
        return []

    # Get all active reservations for that date
    reservations_result = await db.execute(
        select(Reservation).where(
            Reservation.restaurant_id == restaurant_id,
            Reservation.reservation_date == reservation_date,
            Reservation.status.in_(["pending", "confirmed", "seated"]),
            Reservation.table_id.isnot(None),
        )
    )
    existing_reservations = list(reservations_result.scalars().all())

    # Check time overlap for each table
    req_start = datetime.combine(reservation_date, reservation_time)
    req_end = req_start + timedelta(minutes=duration_minutes)

    booked_table_ids = set()
    for res in existing_reservations:
        res_start = datetime.combine(res.reservation_date, res.reservation_time)
        res_end = res_start + timedelta(minutes=res.duration_minutes)
        # Check overlap: two intervals overlap if start1 < end2 AND start2 < end1
        if req_start < res_end and res_start < req_end:
            booked_table_ids.add(res.table_id)

    available = [t for t in all_tables if t.id not in booked_table_ids]
    return available


async def create_reservation(
    db: AsyncSession,
    restaurant_id: uuid.UUID,
    customer_id: uuid.UUID,
    party_size: int,
    reservation_date: date,
    reservation_time: time,
    channel: str = "rest_api",
    duration_minutes: int = 90,
    table_id: uuid.UUID | None = None,
    special_requests: str | None = None,
) -> Reservation:
    reservation = Reservation(
        restaurant_id=restaurant_id,
        customer_id=customer_id,
        table_id=table_id,
        party_size=party_size,
        reservation_date=reservation_date,
        reservation_time=reservation_time,
        duration_minutes=duration_minutes,
        status="pending",
        special_requests=special_requests,
        channel=channel,
    )
    db.add(reservation)
    await db.flush()
    return reservation


async def get_reservation(db: AsyncSession, restaurant_id: uuid.UUID, reservation_id: uuid.UUID) -> Reservation | None:
    result = await db.execute(
        select(Reservation).where(
            Reservation.id == reservation_id,
            Reservation.restaurant_id == restaurant_id,
        )
    )
    return result.scalar_one_or_none()


async def update_reservation_status(db: AsyncSession, reservation: Reservation, status: str) -> Reservation:
    reservation.status = status
    await db.flush()
    return reservation


async def get_available_slots(
    db: AsyncSession,
    restaurant_id: uuid.UUID,
    reservation_date: date,
    party_size: int,
    duration_minutes: int = 90,
    slot_interval_minutes: int = 30,
    open_time: time = time(11, 0),
    close_time: time = time(22, 0),
) -> list[str]:
    """Generate available time slots for a given date and party size."""
    from restaurant_bot.db.models.restaurant import OperatingHours

    # Check operating hours for this day
    day_of_week = reservation_date.weekday()
    hours_result = await db.execute(
        select(OperatingHours).where(
            OperatingHours.restaurant_id == restaurant_id,
            OperatingHours.day_of_week == day_of_week,
        )
    )
    hours = hours_result.scalar_one_or_none()
    if hours:
        if hours.is_closed:
            return []
        open_time = hours.open_time
        close_time = hours.close_time

    available_slots = []
    current = datetime.combine(reservation_date, open_time)
    end_limit = datetime.combine(reservation_date, close_time) - timedelta(minutes=duration_minutes)

    while current <= end_limit:
        slot_time = current.time()
        tables = await check_availability(
            db, restaurant_id, reservation_date, slot_time, party_size, duration_minutes
        )
        if tables:
            available_slots.append(slot_time.strftime("%H:%M"))
        current += timedelta(minutes=slot_interval_minutes)

    return available_slots
