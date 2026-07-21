import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.engine import get_db
from restaurant_bot.auth.permissions import CurrentUser, require_owner
from restaurant_bot.services.analytics_service import get_full_dashboard, get_popular_items

router = APIRouter(prefix="/restaurants/{restaurant_id}/analytics", tags=["analytics"])


@router.get("")
async def get_analytics(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    """Full analytics dashboard data."""
    return await get_full_dashboard(db, restaurant_id)


@router.get("/popular-items")
async def popular_items(
    restaurant_id: uuid.UUID,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    return await get_popular_items(db, restaurant_id, limit=limit)
