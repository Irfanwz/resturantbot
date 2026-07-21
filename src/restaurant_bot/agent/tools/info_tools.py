from pydantic_ai import RunContext
from sqlalchemy import select

from restaurant_bot.agent.deps import RestaurantBotDeps
from restaurant_bot.db.models.conversation import FAQ
from restaurant_bot.db.models.restaurant import OperatingHours


async def get_restaurant_info(ctx: RunContext[RestaurantBotDeps]) -> str:
    """Get general restaurant information (address, phone, hours, features). Use when customer asks about location, contact, hours, etc."""
    config = ctx.deps.config
    restaurant_name = ctx.deps.restaurant_name

    lines = [f"**{restaurant_name}**\n"]

    if config.business.description:
        lines.append(config.business.description + "\n")
    if config.business.cuisine_type:
        lines.append(f"Cuisine: {', '.join(config.business.cuisine_type)}")
    if config.business.address:
        lines.append(f"Address: {config.business.address}")
    if config.business.phone:
        lines.append(f"Phone: {config.business.phone}")
    if config.business.email:
        lines.append(f"Email: {config.business.email}")

    # Operating hours
    result = await ctx.deps.db.execute(
        select(OperatingHours)
        .where(OperatingHours.restaurant_id == ctx.deps.restaurant_id)
        .order_by(OperatingHours.day_of_week)
    )
    hours = result.scalars().all()
    if hours:
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        lines.append("\nOperating Hours:")
        for h in hours:
            if h.is_closed:
                lines.append(f"- {day_names[h.day_of_week]}: Closed")
            else:
                lines.append(f"- {day_names[h.day_of_week]}: {h.open_time.strftime('%H:%M')} - {h.close_time.strftime('%H:%M')}")

    features = []
    if config.business.halal:
        features.append("Halal")
    if config.business.wifi_available:
        features.append("Free WiFi")
    if config.business.parking_available:
        features.append("Parking")
    if config.business.outdoor_seating:
        features.append("Outdoor Seating")
    if config.business.alcohol_served:
        features.append("Alcohol Served")
    if features:
        lines.append(f"\nFeatures: {', '.join(features)}")

    return "\n".join(lines)


async def get_faq_answer(ctx: RunContext[RestaurantBotDeps], question: str) -> str:
    """Search FAQs for an answer to the customer's question. Use when customer asks general questions about the restaurant."""
    db = ctx.deps.db

    result = await db.execute(
        select(FAQ).where(
            FAQ.restaurant_id == ctx.deps.restaurant_id,
            FAQ.is_active == True,
        ).order_by(FAQ.sort_order)
    )
    faqs = result.scalars().all()

    if not faqs:
        return "No FAQs available. Please contact the restaurant directly for more information."

    # Simple keyword matching
    question_lower = question.lower()
    for faq in faqs:
        if any(word in faq.question.lower() for word in question_lower.split() if len(word) > 3):
            return f"**Q: {faq.question}**\nA: {faq.answer}"

    # Return all FAQs if no match
    lines = ["Here are our frequently asked questions:\n"]
    for faq in faqs:
        lines.append(f"**Q: {faq.question}**\nA: {faq.answer}\n")
    return "\n".join(lines)
