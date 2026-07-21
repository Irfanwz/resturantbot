import uuid
from pydantic_ai import RunContext
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from restaurant_bot.agent.deps import RestaurantBotDeps
from restaurant_bot.db.models.menu import MenuCategory, MenuItem


async def get_menu(ctx: RunContext[RestaurantBotDeps]) -> str:
    """Get the full restaurant menu with all categories and items. Use this when a customer asks to see the menu or wants to know what's available."""
    db = ctx.deps.db
    restaurant_id = ctx.deps.restaurant_id

    result = await db.execute(
        select(MenuCategory)
        .where(MenuCategory.restaurant_id == restaurant_id, MenuCategory.is_active == True)
        .options(selectinload(MenuCategory.items).selectinload(MenuItem.modifiers))
        .order_by(MenuCategory.sort_order)
    )
    categories = result.scalars().all()

    if not categories:
        return "The menu is currently empty or not yet set up."

    lines = []
    for cat in categories:
        lines.append(f"\n### {cat.name}")
        if cat.description:
            lines.append(f"_{cat.description}_")
        available_items = [item for item in cat.items if item.is_available]
        if not available_items:
            lines.append("No items currently available in this category.")
            continue
        for item in sorted(available_items, key=lambda x: x.sort_order):
            tags = []
            if item.is_vegetarian:
                tags.append("V")
            if item.is_vegan:
                tags.append("VG")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            lines.append(f"- **{item.name}** — {item.price}{tag_str}")
            if item.description:
                lines.append(f"  {item.description}")
            if item.modifiers:
                for mod in item.modifiers:
                    options_str = ", ".join(
                        f"{opt['name']} (+{opt['price_delta']})" if opt.get('price_delta') else opt['name']
                        for opt in (mod.options if isinstance(mod.options, list) else [])
                    )
                    if options_str:
                        lines.append(f"  {mod.name}: {options_str}")

    return "\n".join(lines)


async def search_menu_items(ctx: RunContext[RestaurantBotDeps], query: str) -> str:
    """Search for specific menu items by name or description. Use this when a customer asks about a specific dish or type of food (e.g., 'pizza', 'vegetarian options', 'spicy')."""
    db = ctx.deps.db
    restaurant_id = ctx.deps.restaurant_id

    result = await db.execute(
        select(MenuItem)
        .where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_available == True,
            MenuItem.name.ilike(f"%{query}%") | MenuItem.description.ilike(f"%{query}%"),
        )
        .options(selectinload(MenuItem.modifiers))
        .limit(15)
    )
    items = result.scalars().all()

    if not items:
        return f"No items found matching '{query}'. Try a different search or ask to see the full menu."

    lines = [f"Found {len(items)} item(s) matching '{query}':\n"]
    for item in items:
        tags = []
        if item.is_vegetarian:
            tags.append("Vegetarian")
        if item.is_vegan:
            tags.append("Vegan")
        tag_str = f" ({', '.join(tags)})" if tags else ""
        lines.append(f"- **{item.name}** — {item.price}{tag_str}")
        if item.description:
            lines.append(f"  {item.description}")
        if item.allergens:
            allergen_list = item.allergens if isinstance(item.allergens, list) else []
            if allergen_list:
                lines.append(f"  Allergens: {', '.join(allergen_list)}")

    return "\n".join(lines)
