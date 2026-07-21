from decimal import Decimal
from pydantic import BaseModel, Field


class AIConfig(BaseModel):
    """How the AI bot behaves and speaks."""
    bot_name: str = "Restaurant Assistant"
    personality: str = "friendly and helpful"
    tone: str = "warm"
    language: str = "en"
    supported_languages: list[str] = Field(default_factory=lambda: ["en"])
    greeting_message: str = "Welcome! How can I help you today?"
    farewell_message: str = "Thank you for visiting! Enjoy your meal!"
    custom_instructions: str = ""
    upsell_enabled: bool = True
    upsell_instructions: str = ""
    max_conversation_turns: int = 50
    fallback_message: str = "I'm not sure about that. Let me connect you with our staff."
    out_of_scope_message: str = "I can only help with our menu, orders, and reservations."


class OrderConfig(BaseModel):
    """Rules for how ordering works."""
    ordering_enabled: bool = True
    order_types: list[str] = Field(default_factory=lambda: ["dine_in", "takeaway"])
    delivery_enabled: bool = False
    delivery_radius_km: float | None = None
    delivery_fee: Decimal = Decimal("0.00")
    delivery_minimum_order: Decimal = Decimal("0.00")
    minimum_order_amount: Decimal = Decimal("0.00")
    tax_rate: Decimal = Decimal("0.00")
    tax_inclusive: bool = False
    tip_enabled: bool = False
    tip_options: list[int] = Field(default_factory=lambda: [10, 15, 20])
    auto_confirm_orders: bool = False
    order_number_prefix: str = "ORD"
    preparation_buffer_minutes: int = 15
    max_items_per_order: int = 50
    special_instructions_enabled: bool = True


class ReservationConfig(BaseModel):
    """Rules for table reservations."""
    reservations_enabled: bool = True
    max_party_size: int = 20
    min_advance_hours: int = 1
    max_advance_days: int = 30
    default_duration_minutes: int = 90
    time_slot_interval_minutes: int = 30
    auto_confirm_reservations: bool = False
    cancellation_policy: str = "Free cancellation up to 2 hours before."
    require_phone_for_reservation: bool = True


class NotificationConfig(BaseModel):
    """How the restaurant gets notified."""
    new_order_notification: bool = True
    notification_channels: list[str] = Field(default_factory=lambda: ["browser"])
    notification_email: str | None = None
    notification_phone: str | None = None
    notification_webhook_url: str | None = None
    daily_summary_enabled: bool = False
    daily_summary_time: str = "22:00"
    telegram_admin_chat_id: str | None = None  # Owner's personal Telegram Chat ID
    # Email SMTP settings
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


class QuickReplyButton(BaseModel):
    """A quick reply button shown in the chat widget."""
    emoji: str = ""
    label: str
    message: str  # what gets sent when customer clicks it


class BrandingConfig(BaseModel):
    """Visual branding for web widget."""
    logo_url: str | None = None
    primary_color: str = "#FF6B35"
    welcome_image_url: str | None = None
    website_url: str | None = None
    social_links: dict[str, str] = Field(default_factory=dict)
    quick_replies: list[QuickReplyButton] = Field(default_factory=lambda: [
        QuickReplyButton(emoji="📋", label="Menu", message="Show me the menu"),
        QuickReplyButton(emoji="🛒", label="Order", message="I want to place an order"),
        QuickReplyButton(emoji="📅", label="Reserve", message="Book a table"),
        QuickReplyButton(emoji="📍", label="Location", message="Where are you located?"),
        QuickReplyButton(emoji="🕐", label="Hours", message="What are your hours?"),
    ])


class BusinessConfig(BaseModel):
    """General business information."""
    address: str = ""
    phone: str = ""
    email: str = ""
    cuisine_type: list[str] = Field(default_factory=list)
    price_range: str = "$$"
    seating_capacity: int | None = None
    parking_available: bool = False
    wifi_available: bool = False
    outdoor_seating: bool = False
    halal: bool = False
    kosher: bool = False
    alcohol_served: bool = False
    description: str = ""


class ChannelConfig(BaseModel):
    """Per-channel settings."""
    whatsapp_enabled: bool = False
    whatsapp_phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    whatsapp_access_token: str | None = None  # Meta Graph API token
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    web_widget_enabled: bool = True
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])


class RestaurantConfig(BaseModel):
    """Master config for a restaurant. Stored as JSON in the restaurants table."""
    ai: AIConfig = Field(default_factory=AIConfig)
    ordering: OrderConfig = Field(default_factory=OrderConfig)
    reservations: ReservationConfig = Field(default_factory=ReservationConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    branding: BrandingConfig = Field(default_factory=BrandingConfig)
    business: BusinessConfig = Field(default_factory=BusinessConfig)
    channels: ChannelConfig = Field(default_factory=ChannelConfig)


# Preset configurations for quick setup
CONFIG_PRESETS = {
    "casual": {
        "name": "Casual & Friendly",
        "description": "Relaxed, uses casual language, great for cafes and fast food",
        "preview_greeting": "Hey! Welcome! What can I get for you today?",
        "config": {
            "ai": {
                "bot_name": "Buddy",
                "personality": "casual and fun",
                "tone": "playful",
                "greeting_message": "Hey! Welcome! What can I get for you today?",
            }
        },
    },
    "professional": {
        "name": "Professional",
        "description": "Polite, clear, business-like — great for family restaurants",
        "preview_greeting": "Welcome! How may I assist you today?",
        "config": {
            "ai": {
                "personality": "professional and helpful",
                "tone": "warm",
                "greeting_message": "Welcome! How may I assist you today?",
            }
        },
    },
    "formal": {
        "name": "Fine Dining",
        "description": "Elegant, sophisticated — perfect for upscale restaurants",
        "preview_greeting": "Good evening. Welcome to our establishment. How may I be of service?",
        "config": {
            "ai": {
                "bot_name": "Concierge",
                "personality": "elegant and knowledgeable",
                "tone": "formal",
                "greeting_message": "Good evening. Welcome to our establishment. How may I be of service?",
            }
        },
    },
    "quick": {
        "name": "Fast & Efficient",
        "description": "Short responses, order-focused — ideal for delivery/cloud kitchens",
        "preview_greeting": "Hi! Ready to order? Tell me what you'd like!",
        "config": {
            "ai": {
                "personality": "efficient and quick",
                "tone": "direct",
                "greeting_message": "Hi! Ready to order? Tell me what you'd like!",
            }
        },
    },
}
