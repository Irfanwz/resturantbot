import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.engine import get_db
from restaurant_bot.auth.permissions import CurrentUser, require_staff
from restaurant_bot.schemas.menu import (
    MenuCategoryCreate, MenuCategoryUpdate, MenuCategoryResponse,
    MenuItemCreate, MenuItemUpdate, MenuItemResponse, MenuResponse,
)
from restaurant_bot.services import menu_service
from restaurant_bot.db.models.restaurant import Restaurant
from sqlalchemy import select

router = APIRouter(prefix="/restaurants/{restaurant_id}/menu", tags=["menu"])


@router.get("", response_model=MenuResponse)
async def get_menu(restaurant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get full menu (public - no auth required)."""
    result = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    categories = await menu_service.get_full_menu(db, restaurant_id)
    return MenuResponse(
        restaurant_name=restaurant.name,
        currency=restaurant.currency,
        categories=[MenuCategoryResponse.model_validate(c) for c in categories],
    )


@router.post("/categories", response_model=MenuCategoryResponse)
async def create_category(
    restaurant_id: uuid.UUID,
    req: MenuCategoryCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    category = await menu_service.create_category(
        db, restaurant_id, name=req.name, description=req.description, sort_order=req.sort_order
    )
    return MenuCategoryResponse.model_validate(category)


@router.patch("/categories/{category_id}", response_model=MenuCategoryResponse)
async def update_category(
    restaurant_id: uuid.UUID,
    category_id: uuid.UUID,
    req: MenuCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    category = await menu_service.get_category(db, restaurant_id, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    updated = await menu_service.update_category(db, category, **req.model_dump(exclude_none=True))
    return MenuCategoryResponse.model_validate(updated)


@router.delete("/categories/{category_id}")
async def delete_category(
    restaurant_id: uuid.UUID,
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    category = await menu_service.get_category(db, restaurant_id, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    await menu_service.delete_category(db, category)
    return {"message": "Category deleted"}


@router.post("/items", response_model=MenuItemResponse)
async def create_item(
    restaurant_id: uuid.UUID,
    req: MenuItemCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    item = await menu_service.create_menu_item(db, restaurant_id, **req.model_dump())
    return MenuItemResponse.model_validate(item)


@router.patch("/items/{item_id}", response_model=MenuItemResponse)
async def update_item(
    restaurant_id: uuid.UUID,
    item_id: uuid.UUID,
    req: MenuItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    item = await menu_service.get_menu_item(db, restaurant_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    updated = await menu_service.update_menu_item(db, item, **req.model_dump(exclude_none=True))
    return MenuItemResponse.model_validate(updated)


@router.delete("/items/{item_id}")
async def delete_item(
    restaurant_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
):
    item = await menu_service.get_menu_item(db, restaurant_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await menu_service.delete_menu_item(db, item)
    return {"message": "Item deleted"}
