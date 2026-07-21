import uuid
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from restaurant_bot.db.engine import get_db
from restaurant_bot.db.models.order import Order
from restaurant_bot.auth.permissions import CurrentUser, require_staff
from restaurant_bot.schemas.order import OrderResponse, OrderStatusUpdate
from restaurant_bot.services.order_service import get_order, update_order_status
from restaurant_bot.services.analytics_service import get_order_stats

router = APIRouter(prefix="/restaurants/{restaurant_id}/orders", tags=["orders"])


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    restaurant_id: uuid.UUID,
    status: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    query = select(Order).where(Order.restaurant_id == restaurant_id).options(selectinload(Order.items)).order_by(Order.placed_at.desc()).limit(50)
    if status:
        query = query.where(Order.status == status)
    if from_date:
        query = query.where(Order.placed_at >= datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc))
    if to_date:
        query = query.where(Order.placed_at <= datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc))
    result = await db.execute(query)
    orders = result.scalars().all()
    return [OrderResponse.model_validate(o) for o in orders]


@router.get("/stats/summary")
async def order_stats(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    return await get_order_stats(db, restaurant_id)


@router.get("/new", response_model=list[OrderResponse])
async def get_new_orders(
    restaurant_id: uuid.UUID,
    since: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    """Get orders placed after a given timestamp. Used for real-time polling."""
    query = (
        select(Order)
        .where(Order.restaurant_id == restaurant_id)
        .options(selectinload(Order.items))
        .order_by(Order.placed_at.desc())
        .limit(20)
    )
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query = query.where(Order.placed_at > since_dt)
        except ValueError:
            pass
    else:
        # Default: orders from last 5 minutes
        five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        query = query.where(Order.placed_at > five_min_ago)

    result = await db.execute(query)
    orders = result.scalars().all()
    return [OrderResponse.model_validate(o) for o in orders]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order_detail(
    restaurant_id: uuid.UUID,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    order = await get_order(db, restaurant_id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse.model_validate(order)


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_status(
    restaurant_id: uuid.UUID,
    order_id: uuid.UUID,
    req: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    order = await get_order(db, restaurant_id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    valid_statuses = ["pending", "confirmed", "preparing", "ready", "delivered", "cancelled"]
    if req.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    updated = await update_order_status(db, order, req.status)
    return OrderResponse.model_validate(updated)


class CancelOrderRequest(BaseModel):
    reason: str | None = None


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    restaurant_id: uuid.UUID,
    order_id: uuid.UUID,
    req: CancelOrderRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    order = await get_order(db, restaurant_id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status in ("delivered", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel order with status '{order.status}'")
    if req and req.reason:
        order.special_instructions = f"{order.special_instructions or ''}\n[CANCELLED: {req.reason}]".strip()
    updated = await update_order_status(db, order, "cancelled")
    return OrderResponse.model_validate(updated)
