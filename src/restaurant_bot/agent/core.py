from pydantic_ai import Agent, RunContext
from pydantic_ai.models import KnownModelName

from restaurant_bot.agent.deps import RestaurantBotDeps
from restaurant_bot.agent.tools.menu_tools import get_menu, search_menu_items
from restaurant_bot.agent.tools.order_tools import add_to_cart, remove_from_cart, get_cart, place_order, get_order_status, update_cart_quantity, get_my_orders
from restaurant_bot.agent.tools.reservation_tools import check_table_availability, make_reservation, cancel_reservation
from restaurant_bot.agent.tools.info_tools import get_restaurant_info, get_faq_answer
from restaurant_bot.agent.prompts.system import build_system_prompt
from restaurant_bot.config import settings


def build_agent() -> Agent[RestaurantBotDeps]:
    """Build the agent with the configured model and all tools."""
    import os

    provider = settings.llm_provider
    api_key = settings.llm_api_key
    model = settings.llm_model
    base_url = settings.llm_base_url

    tools = [
        get_menu,
        search_menu_items,
        add_to_cart,
        remove_from_cart,
        get_cart,
        place_order,
        get_order_status,
        update_cart_quantity,
        get_my_orders,
        check_table_availability,
        make_reservation,
        cancel_reservation,
        get_restaurant_info,
        get_faq_answer,
    ]

    if provider == "groq":
        # Groq uses OpenAI Chat Completions API (not Responses API)
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_BASE_URL"] = base_url or "https://api.groq.com/openai/v1"
        from pydantic_ai.models.openai import OpenAIChatModelSettings
        return Agent(
            model=f"openai-chat:{model}",
            deps_type=RestaurantBotDeps,
            tools=tools,
            model_settings=OpenAIChatModelSettings(parallel_tool_calls=False),
        )
    elif provider == "openai":
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        if base_url:
            os.environ["OPENAI_BASE_URL"] = base_url
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        return Agent(model=f"openai:{model}", deps_type=RestaurantBotDeps, tools=tools)
    else:
        # Anthropic / Google
        if api_key:
            if provider == "anthropic":
                os.environ["ANTHROPIC_API_KEY"] = api_key
        return Agent(model=f"{provider}:{model}", deps_type=RestaurantBotDeps, tools=tools)


restaurant_agent = build_agent()


@restaurant_agent.system_prompt
async def dynamic_system_prompt(ctx: RunContext[RestaurantBotDeps]) -> str:
    """Build the system prompt dynamically from the restaurant's config."""
    from sqlalchemy import select
    from restaurant_bot.db.models.menu import MenuCategory

    # Build menu summary
    result = await ctx.deps.db.execute(
        select(MenuCategory)
        .where(MenuCategory.restaurant_id == ctx.deps.restaurant_id, MenuCategory.is_active == True)
        .order_by(MenuCategory.sort_order)
    )
    categories = result.scalars().all()
    menu_summary = ", ".join(cat.name for cat in categories) if categories else "Menu not yet configured"

    return build_system_prompt(
        restaurant_name=ctx.deps.restaurant_name,
        config=ctx.deps.config,
        menu_summary=f"Available categories: {menu_summary}",
    )


async def chat_with_agent(deps: RestaurantBotDeps, message: str) -> str:
    """Run a conversation turn with the restaurant agent."""
    from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart

    # Build message history from session as proper Pydantic AI message objects
    message_history: list[ModelRequest | ModelResponse] = []
    for msg in deps.session.conversation_history:
        if msg["role"] == "user":
            message_history.append(
                ModelRequest(parts=[UserPromptPart(content=msg["content"])])
            )
        elif msg["role"] == "assistant":
            message_history.append(
                ModelResponse(parts=[TextPart(content=msg["content"])])
            )

    result = await restaurant_agent.run(
        message,
        deps=deps,
        message_history=message_history if message_history else None,
    )

    # Save to session history
    deps.session.add_message("user", message)
    deps.session.add_message("assistant", result.output)

    return result.output
