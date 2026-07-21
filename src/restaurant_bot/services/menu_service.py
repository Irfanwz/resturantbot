import uuid
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from restaurant_bot.db.models.menu import MenuCategory, MenuItem, MenuItemModifier


async def get_full_menu(db: AsyncSession, restaurant_id: uuid.UUID) -> list[MenuCategory]:
    result = await db.execute(
        select(MenuCategory)
        .where(MenuCategory.restaurant_id == restaurant_id, MenuCategory.is_active == True)
        .options(selectinload(MenuCategory.items).selectinload(MenuItem.modifiers))
        .order_by(MenuCategory.sort_order)
    )
    return list(result.scalars().all())


async def get_category(db: AsyncSession, restaurant_id: uuid.UUID, category_id: uuid.UUID) -> MenuCategory | None:
    result = await db.execute(
        select(MenuCategory)
        .where(MenuCategory.id == category_id, MenuCategory.restaurant_id == restaurant_id)
        .options(selectinload(MenuCategory.items).selectinload(MenuItem.modifiers))
    )
    return result.scalar_one_or_none()


async def create_category(db: AsyncSession, restaurant_id: uuid.UUID, name: str, description: str | None = None, sort_order: int = 0) -> MenuCategory:
    category = MenuCategory(
        restaurant_id=restaurant_id,
        name=name,
        description=description,
        sort_order=sort_order,
    )
    db.add(category)
    await db.flush()
    return category


async def update_category(db: AsyncSession, category: MenuCategory, **kwargs) -> MenuCategory:
    for key, value in kwargs.items():
        if value is not None:
            setattr(category, key, value)
    await db.flush()
    return category


async def delete_category(db: AsyncSession, category: MenuCategory) -> None:
    await db.delete(category)
    await db.flush()


async def get_menu_item(db: AsyncSession, restaurant_id: uuid.UUID, item_id: uuid.UUID) -> MenuItem | None:
    result = await db.execute(
        select(MenuItem)
        .where(MenuItem.id == item_id, MenuItem.restaurant_id == restaurant_id)
        .options(selectinload(MenuItem.modifiers))
    )
    return result.scalar_one_or_none()


async def create_menu_item(db: AsyncSession, restaurant_id: uuid.UUID, **kwargs) -> MenuItem:
    item = MenuItem(restaurant_id=restaurant_id, **kwargs)
    db.add(item)
    await db.flush()
    return item


async def update_menu_item(db: AsyncSession, item: MenuItem, **kwargs) -> MenuItem:
    for key, value in kwargs.items():
        if value is not None:
            setattr(item, key, value)
    await db.flush()
    return item


async def delete_menu_item(db: AsyncSession, item: MenuItem) -> None:
    await db.delete(item)
    await db.flush()


async def search_menu_items(db: AsyncSession, restaurant_id: uuid.UUID, query: str) -> list[MenuItem]:
    result = await db.execute(
        select(MenuItem)
        .where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_available == True,
            MenuItem.name.ilike(f"%{query}%"),
        )
        .options(selectinload(MenuItem.modifiers))
        .limit(20)
    )
    return list(result.scalars().all())
