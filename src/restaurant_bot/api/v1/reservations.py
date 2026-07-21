import uuid
from datetime import date, time, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from restaurant_bot.db.engine import get_db
from restaurant_bot.db.models.reservation import Reservation
from restaurant_bot.auth.permissions import CurrentUser, require_staff
from restaurant_bot.schemas.reservation import (
    ReservationResponse, ReservationStatusUpdate,
    AvailabilityRequest, AvailabilityResponse,
    ReservationCreate,
)
from restaurant_bot.services.reservation_service import (
    get_reservation, update_reservation_status,
    check_availability, get_available_slots, create_reservation,
)
from restaurant_bot.services.order_service import get_or_create_customer
from restaurant_bot.services.config_service import config_service

router = APIRouter(prefix="/restaurants/{restaurant_id}/reservations", tags=["reservations"])


@router.get("", response_model=list[ReservationResponse])
async def list_reservations(
    restaurant_id: uuid.UUID,
    status: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    query = (
        select(Reservation)
        .where(Reservation.restaurant_id == restaurant_id)
        .order_by(Reservation.reservation_date.desc(), Reservation.reservation_time.desc())
        .limit(50)
    )
    if status:
        query = query.where(Reservation.status == status)
    if from_date:
        query = query.where(Reservation.reservation_date >= from_date)
    if to_date:
        query = query.where(Reservation.reservation_date <= to_date)
    result = await db.execute(query)
    reservations = result.scalars().all()
    return [ReservationResponse.model_validate(r) for r in reservations]


@router.post("/check-availability", response_model=AvailabilityResponse)
async def check_availability_endpoint(
    restaurant_id: uuid.UUID,
    req: AvailabilityRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint to check table availability."""
    config = await config_service.get_config(db, restaurant_id)
    if not config.reservations.reservations_enabled:
        return AvailabilityResponse(available=False, message="Reservations are not available.")

    tables = await check_availability(
        db, restaurant_id, req.date, req.time, req.party_size,
        config.reservations.default_duration_minutes,
    )

    if tables:
        slots = await get_available_slots(
            db, restaurant_id, req.date, req.party_size,
            config.reservations.default_duration_minutes,
            config.reservations.time_slot_interval_minutes,
        )
        return AvailabilityResponse(
            available=True,
            available_slots=slots,
            message=f"{len(tables)} table(s) available at {req.time.strftime('%H:%M')}.",
        )
    else:
        slots = await get_available_slots(
            db, restaurant_id, req.date, req.party_size,
            config.reservations.default_duration_minutes,
            config.reservations.time_slot_interval_minutes,
        )
        msg = f"No tables available at {req.time.strftime('%H:%M')}."
        if slots:
            msg += f" Try: {', '.join(slots[:5])}"
        return AvailabilityResponse(available=False, available_slots=slots, message=msg)


@router.post("", response_model=ReservationResponse)
async def create_reservation_endpoint(
    restaurant_id: uuid.UUID,
    req: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    """Admin endpoint to create a reservation."""
    config = await config_service.get_config(db, restaurant_id)

    tables = await check_availability(
        db, restaurant_id, req.reservation_date, req.reservation_time,
        req.party_size, config.reservations.default_duration_minutes,
    )
    if not tables:
        raise HTTPException(status_code=400, detail="No tables available for this time slot")

    customer = await get_or_create_customer(
        db, restaurant_id, "admin", "admin-created",
        name=req.customer_name, phone=req.customer_phone,
    )

    reservation = await create_reservation(
        db=db,
        restaurant_id=restaurant_id,
        customer_id=customer.id,
        party_size=req.party_size,
        reservation_date=req.reservation_date,
        reservation_time=req.reservation_time,
        channel="admin",
        duration_minutes=config.reservations.default_duration_minutes,
        table_id=tables[0].id,
        special_requests=req.special_requests,
    )
    return ReservationResponse.model_validate(reservation)


@router.get("/{reservation_id}", response_model=ReservationResponse)
async def get_reservation_detail(
    restaurant_id: uuid.UUID,
    reservation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    reservation = await get_reservation(db, restaurant_id, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return ReservationResponse.model_validate(reservation)


@router.patch("/{reservation_id}/status", response_model=ReservationResponse)
async def update_status(
    restaurant_id: uuid.UUID,
    reservation_id: uuid.UUID,
    req: ReservationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    reservation = await get_reservation(db, restaurant_id, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    valid_statuses = ["pending", "confirmed", "seated", "completed", "cancelled", "no_show"]
    if req.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    updated = await update_reservation_status(db, reservation, req.status)
    return ReservationResponse.model_validate(updated)
