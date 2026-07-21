import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.engine import get_db
from restaurant_bot.auth.permissions import CurrentUser, require_owner
from restaurant_bot.schemas.config import RestaurantConfig, CONFIG_PRESETS
from restaurant_bot.services.config_service import config_service
from restaurant_bot.agent.prompts.system import build_system_prompt

router = APIRouter(prefix="/restaurants/{restaurant_id}/config", tags=["config"])


@router.get("", response_model=RestaurantConfig)
async def get_config(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    return await config_service.get_config(db, restaurant_id)


@router.put("", response_model=RestaurantConfig)
async def update_full_config(
    restaurant_id: uuid.UUID,
    config: RestaurantConfig,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    return await config_service.update_config(db, restaurant_id, config)


@router.patch("/{section}", response_model=RestaurantConfig)
async def update_config_section(
    restaurant_id: uuid.UUID,
    section: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    valid_sections = ["ai", "ordering", "reservations", "notifications", "branding", "business", "channels"]
    if section not in valid_sections:
        raise HTTPException(status_code=400, detail=f"Invalid section. Must be one of: {valid_sections}")
    return await config_service.update_config_section(db, restaurant_id, section, data)


@router.get("/presets")
async def get_presets():
    """Get available configuration presets."""
    return CONFIG_PRESETS


@router.post("/apply-preset", response_model=RestaurantConfig)
async def apply_preset(
    restaurant_id: uuid.UUID,
    preset_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    if preset_id not in CONFIG_PRESETS:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")

    preset = CONFIG_PRESETS[preset_id]
    current = await config_service.get_config(db, restaurant_id)

    # Merge preset config into current config
    preset_data = preset["config"]
    for section_name, section_data in preset_data.items():
        section_model = getattr(current, section_name)
        updated_section = section_model.model_copy(update=section_data)
        current = current.model_copy(update={section_name: updated_section})

    return await config_service.update_config(db, restaurant_id, current)


@router.get("/preview-prompt")
async def preview_prompt(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_owner),
):
    """Preview the system prompt the AI agent will use."""
    from sqlalchemy import select
    from restaurant_bot.db.models.restaurant import Restaurant

    result = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    config = await config_service.get_config(db, restaurant_id)
    prompt = build_system_prompt(
        restaurant_name=restaurant.name,
        config=config,
        menu_summary="[Menu will be loaded dynamically at runtime]",
    )
    return {"system_prompt": prompt}
