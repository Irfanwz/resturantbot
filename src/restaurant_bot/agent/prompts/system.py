from restaurant_bot.schemas.config import RestaurantConfig


def build_system_prompt(
    restaurant_name: str,
    config: RestaurantConfig,
    menu_summary: str,
    operating_hours: str = "Not specified",
) -> str:
    sections = []

    # Identity
    sections.append(f"""You are {config.ai.bot_name}, the AI assistant for {restaurant_name}.
{config.business.description if config.business.description else ''}""")

    # Personality
    sections.append(f"""## Your Personality
- Be {config.ai.personality} in every response
- Tone: {config.ai.tone}
- Primary language: {config.ai.language}
- Supported languages: {', '.join(config.ai.supported_languages)}
- When a customer starts a conversation, greet them with: "{config.ai.greeting_message}"
- When a conversation ends, say: "{config.ai.farewell_message}" """)

    # Capabilities
    capabilities = ["- Answering questions about our menu and making recommendations"]
    if config.ordering.ordering_enabled:
        order_types = ", ".join(config.ordering.order_types)
        if config.ordering.delivery_enabled:
            order_types += ", delivery"
        capabilities.append(f"- Taking food orders ({order_types})")
        capabilities.append("- Managing the customer's cart (add, remove, modify items)")
        capabilities.append("- Checking order status")
    if config.reservations.reservations_enabled:
        capabilities.append(f"- Table reservations (up to {config.reservations.max_party_size} guests)")
    capabilities.append("- Answering FAQs and general restaurant information")

    sections.append("## What You Can Help With\n" + "\n".join(capabilities))

    # Business rules
    rules = []
    if config.ordering.ordering_enabled:
        if config.ordering.minimum_order_amount > 0:
            rules.append(f"- Minimum order amount: {config.ordering.minimum_order_amount}")
        if config.ordering.delivery_enabled:
            rules.append(f"- Delivery fee: {config.ordering.delivery_fee}")
            if config.ordering.delivery_minimum_order > 0:
                rules.append(f"- Minimum delivery order: {config.ordering.delivery_minimum_order}")
            if config.ordering.delivery_radius_km:
                rules.append(f"- Delivery radius: {config.ordering.delivery_radius_km} km")
        if config.ordering.tax_rate > 0:
            tax_pct = float(config.ordering.tax_rate) * 100
            inclusive = " (included in prices)" if config.ordering.tax_inclusive else " (added to total)"
            rules.append(f"- Tax: {tax_pct}%{inclusive}")
    if config.reservations.reservations_enabled:
        rules.append(f"- Reservations must be made at least {config.reservations.min_advance_hours} hour(s) in advance")
        rules.append(f"- Maximum party size: {config.reservations.max_party_size}")
        rules.append(f"- Cancellation policy: {config.reservations.cancellation_policy}")

    rules.append(f"- Operating hours: {operating_hours}")

    if rules:
        sections.append("## Business Rules\n" + "\n".join(rules))

    # Menu
    sections.append(f"## Menu Overview\n{menu_summary}")

    # Custom instructions
    if config.ai.custom_instructions:
        sections.append(f"## Special Instructions from the Owner\n{config.ai.custom_instructions}")

    # Upselling
    if config.ai.upsell_enabled:
        upsell_text = "When appropriate, suggest complementary items to enhance the customer's order."
        if config.ai.upsell_instructions:
            upsell_text += f"\n{config.ai.upsell_instructions}"
        sections.append(f"## Upselling\n{upsell_text}")

    # Business info
    info_parts = []
    if config.business.address:
        info_parts.append(f"- Address: {config.business.address}")
    if config.business.phone:
        info_parts.append(f"- Phone: {config.business.phone}")
    if config.business.cuisine_type:
        info_parts.append(f"- Cuisine: {', '.join(config.business.cuisine_type)}")
    if config.business.halal:
        info_parts.append("- Halal certified")
    if config.business.wifi_available:
        info_parts.append("- Free WiFi available")
    if config.business.parking_available:
        info_parts.append("- Parking available")
    if config.business.outdoor_seating:
        info_parts.append("- Outdoor seating available")
    if info_parts:
        sections.append("## Restaurant Information\n" + "\n".join(info_parts))

    # Hard rules
    sections.append(f"""## Critical Rules
- ONLY recommend items returned by your menu tools. NEVER invent or hallucinate menu items.
- ALWAYS use the appropriate tool to look up menu items, place orders, or make reservations.
- If a customer asks something outside your scope, say: "{config.ai.out_of_scope_message}"
- If you cannot help, say: "{config.ai.fallback_message}"
- Be {config.ai.personality} and {config.ai.tone} in every response.
- Keep responses concise and helpful.""")

    return "\n\n".join(sections)
