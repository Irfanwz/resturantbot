# Restaurant AI Bot — Complete Implementation Plan

## Context
Building a plug-and-play, channel-agnostic, **fully configurable per-restaurant** AI bot as a SaaS product. The bot handles menu queries, conversational ordering, table reservations, and order tracking. Every restaurant gets their own personality, rules, and behavior — zero code changes. WhatsApp integration comes later — architecture is channel-agnostic from day 1. Target: sell to restaurants at $39-99/month.

---

## Tech Stack (Final Decision)

| Layer | Choice | Why |
|-------|--------|-----|
| **Language** | Python 3.12+ (only) | AI ecosystem is Python-first. Pydantic AI, FastAPI, SQLAlchemy — all best-in-class Python. Single language = one deploy pipeline. |
| **API Framework** | FastAPI + Uvicorn | Auto OpenAPI docs, native async, Pydantic v2 built-in. Any frontend dev can integrate without writing docs. |
| **AI Agent** | Pydantic AI | Type-safe tools, model-agnostic (Claude/GPT/Gemini), RunContext for multi-tenancy, no framework lock-in. |
| **ORM** | SQLAlchemy 2.0 (async) + Alembic | Supports SQLite/PostgreSQL/MySQL by changing one env var. Alembic handles migrations across all DBs. |
| **Session Store** | In-memory (dev) → Redis (prod) | Pluggable via interface. Start simple, scale when needed. |
| **Package Manager** | uv | 100x faster than pip. `uv sync` and you're running. |
| **Auth** | JWT (python-jose + passlib) | Stateless, no external service dependency. |
| **HTTP Client** | httpx | For outbound calls (WhatsApp API, webhooks, etc.) |
| **Containerization** | Docker + docker-compose | One command deploy anywhere. |

**No JavaScript/TypeScript needed.** Python handles everything — API, AI, database, deployment.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                  CHANNEL LAYER                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ REST API │  │ WhatsApp │  │ Telegram │  (future) │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       └──────────────┼─────────────┘                │
│              ┌───────▼───────┐                      │
│              │ Message Router│ normalize → canonical │
│              └───────┬───────┘                      │
├──────────────────────┼──────────────────────────────┤
│              ┌───────▼───────┐                      │
│              │Session Manager│ cart + history        │
│              └───────┬───────┘                      │
│              ┌───────▼───────┐                      │
│              │ AI AGENT CORE │ Pydantic AI           │
│              │  (claude/gpt) │                       │
│              └───────┬───────┘                      │
│         ┌────────────┼────────────┐                 │
│    ┌────▼────┐ ┌─────▼────┐ ┌────▼─────┐          │
│    │Menu     │ │Order     │ │Reservation│          │
│    │Tools    │ │Tools     │ │Tools      │          │
│    └────┬────┘ └─────┬────┘ └────┬─────┘          │
│         └────────────┼────────────┘                 │
│              ┌───────▼───────┐                      │
│              │  SERVICES     │ business logic        │
│              └───────┬───────┘                      │
│              ┌───────▼───────┐                      │
│              │  DATABASE     │ SQLAlchemy async      │
│              │  SQLite/PG/MY │                       │
│              └───────────────┘                      │
└─────────────────────────────────────────────────────┘
```

### Channel-Agnostic Design (Core Innovation)

The **canonical message format** is the contract between channels and intelligence:

```python
@dataclass
class IncomingMessage:
    channel: str              # "rest_api", "whatsapp", "telegram"
    sender_id: str            # channel-specific user identifier
    restaurant_id: str        # which restaurant this is for
    text: str | None          # text content
    media_url: str | None     # image/document URL if any
    metadata: dict            # channel-specific extras
    timestamp: datetime

@dataclass
class OutgoingMessage:
    recipient_id: str
    text: str
    buttons: list[Button] | None      # rendered differently per channel
    media: list[Media] | None
    metadata: dict
```

Each channel adapter implements **two methods**:
1. `normalize(raw_payload) -> IncomingMessage`
2. `render(OutgoingMessage) -> channel_specific_response`

**Adding WhatsApp later = writing ONE file.** Zero changes to agent, tools, or database.

---

## AI Agent Design (Pydantic AI)

```python
# The dependency context carried through every agent call
@dataclass
class RestaurantBotDeps:
    db: AsyncSession
    restaurant_id: uuid.UUID
    session_id: str
    customer_id: uuid.UUID | None
    restaurant_config: RestaurantConfig  # cached settings

# The agent definition
restaurant_agent = Agent(
    model="claude-sonnet-4-20250514",  # configurable per restaurant
    deps_type=RestaurantBotDeps,
    system_prompt=dynamic_system_prompt,  # loaded per-restaurant from DB
    tools=[
        get_menu,
        search_menu_items,
        add_to_cart,
        remove_from_cart,
        get_cart,
        place_order,
        get_order_status,
        check_table_availability,
        make_reservation,
        cancel_reservation,
        get_restaurant_info,
        get_faq_answer,
    ],
    output_type=AgentResponse,
)
```

**Dynamic system prompt per restaurant:**
```
You are {restaurant_name}'s AI assistant.
You help customers with: ordering food, table reservations, order tracking, and general questions.
Restaurant hours: {hours}
Special instructions: {owner_custom_instructions}
Current menu categories: {categories}
```

---

## Multi-Tenant Architecture

**Approach: Shared database, shared schema, `restaurant_id` column on every table.**

```python
class TenantMixin:
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id"), index=True
    )

class TenantQuery:
    @staticmethod
    def scoped(query, restaurant_id: uuid.UUID):
        return query.filter_by(restaurant_id=restaurant_id)
```

**Tenant resolution per channel:**
- REST API: `restaurant_id` in URL path (`/api/v1/restaurants/{restaurant_id}/chat`)
- WhatsApp: mapped from WhatsApp Business phone number → restaurant_id
- Telegram: mapped from bot token → restaurant_id

---

## Per-Restaurant Configuration System (Core Feature)

Every restaurant is **fully configurable** — personality, business rules, features, and behavior. All stored in the DB, editable via admin API, applied at runtime. **Zero code changes to customize a restaurant.**

### Configuration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              RESTAURANT CONFIG (DB: JSON columns)            │
│                                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐    │
│  │ AI Config    │ │ Business     │ │ Feature Toggles  │    │
│  │ personality  │ │ Rules        │ │ ordering: on/off  │    │
│  │ tone, lang   │ │ min order    │ │ reservations: on  │    │
│  │ greeting     │ │ delivery     │ │ delivery: off     │    │
│  │ instructions │ │ tax, tips    │ │ reviews: on       │    │
│  └──────┬───────┘ └──────┬───────┘ └────────┬─────────┘    │
│         └────────────────┼──────────────────┘               │
│                   ┌──────▼───────┐                           │
│                   │  Config      │                           │
│                   │  Loader      │ cached in memory/Redis    │
│                   └──────┬───────┘                           │
│                   ┌──────▼───────┐                           │
│                   │ Dynamic      │                           │
│                   │ System Prompt│ built per-restaurant      │
│                   └──────┬───────┘                           │
│                   ┌──────▼───────┐                           │
│                   │ AI Agent     │ behaves differently       │
│                   │ (per tenant) │ for each restaurant       │
│                   └──────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

### RestaurantConfig — Full Configuration Schema

This Pydantic model defines EVERYTHING a restaurant owner can customize:

```python
class AIConfig(BaseModel):
    """How the AI bot behaves and speaks."""
    bot_name: str = "Restaurant Assistant"
    personality: str = "friendly and helpful"       # "formal", "casual", "funny", "professional"
    tone: str = "warm"                              # "warm", "formal", "playful", "direct"
    language: str = "en"                            # primary language: "en", "ar", "ur", "es", "fr", etc.
    supported_languages: list[str] = ["en"]         # multi-language support
    greeting_message: str = "Welcome! How can I help you today?"
    farewell_message: str = "Thank you for visiting! Enjoy your meal!"
    custom_instructions: str = ""                   # owner writes free-form instructions for the AI
    # Example: "Always suggest our special biryani. Never recommend competitor restaurants."
    upsell_enabled: bool = True                     # suggest add-ons, combos, popular items
    upsell_instructions: str = ""                   # "When someone orders a burger, suggest fries and a drink"
    max_conversation_turns: int = 50                # prevent runaway conversations
    fallback_message: str = "I'm not sure about that. Let me connect you with our staff."
    out_of_scope_message: str = "I can only help with our menu, orders, and reservations."

class OrderConfig(BaseModel):
    """Rules for how ordering works."""
    ordering_enabled: bool = True
    order_types: list[str] = ["dine_in", "takeaway"]  # which types this restaurant supports
    delivery_enabled: bool = False
    delivery_radius_km: float | None = None
    delivery_fee: Decimal = Decimal("0.00")
    delivery_minimum_order: Decimal = Decimal("0.00")
    minimum_order_amount: Decimal = Decimal("0.00")    # for any order type
    tax_rate: Decimal = Decimal("0.00")                # e.g., 0.08 for 8% tax
    tax_inclusive: bool = False                         # prices include tax or added on top?
    tip_enabled: bool = False
    tip_options: list[int] = [10, 15, 20]              # percentage options
    auto_confirm_orders: bool = False                   # auto-confirm or require staff approval?
    order_number_prefix: str = "ORD"                    # "ORD-0042" or "BRG-0042" for a burger place
    preparation_buffer_minutes: int = 15               # added to estimated time
    max_items_per_order: int = 50
    special_instructions_enabled: bool = True          # allow customers to add notes?

class ReservationConfig(BaseModel):
    """Rules for table reservations."""
    reservations_enabled: bool = True
    max_party_size: int = 20
    min_advance_hours: int = 1                         # must book at least 1 hour ahead
    max_advance_days: int = 30                         # can book up to 30 days ahead
    default_duration_minutes: int = 90
    time_slot_interval_minutes: int = 30               # slots every 30 min
    auto_confirm_reservations: bool = False
    cancellation_policy: str = "Free cancellation up to 2 hours before."
    require_phone_for_reservation: bool = True

class NotificationConfig(BaseModel):
    """How the restaurant gets notified of new orders/reservations."""
    new_order_notification: bool = True
    notification_channels: list[str] = ["email"]       # "email", "whatsapp", "sms", "webhook"
    notification_email: str | None = None
    notification_phone: str | None = None              # for WhatsApp/SMS alerts to owner
    notification_webhook_url: str | None = None        # POST to external system (POS, etc.)
    daily_summary_enabled: bool = False
    daily_summary_time: str = "22:00"                  # send daily report at this time

class BrandingConfig(BaseModel):
    """Visual branding (for web widget / future dashboard)."""
    logo_url: str | None = None
    primary_color: str = "#FF6B35"                     # brand color
    welcome_image_url: str | None = None
    website_url: str | None = None
    social_links: dict[str, str] = {}                  # {"instagram": "...", "facebook": "..."}

class BusinessConfig(BaseModel):
    """General business information."""
    address: str = ""
    phone: str = ""
    email: str = ""
    cuisine_type: list[str] = []                       # ["Italian", "Pizza", "Pasta"]
    price_range: str = "$$"                            # "$", "$$", "$$$", "$$$$"
    seating_capacity: int | None = None
    parking_available: bool = False
    wifi_available: bool = False
    outdoor_seating: bool = False
    halal: bool = False
    kosher: bool = False
    alcohol_served: bool = False
    description: str = ""                              # about the restaurant

class ChannelConfig(BaseModel):
    """Per-channel settings."""
    whatsapp_enabled: bool = False
    whatsapp_phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    web_widget_enabled: bool = True
    allowed_origins: list[str] = ["*"]                 # CORS for web widget

class RestaurantConfig(BaseModel):
    """THE master config — one per restaurant, stored in DB."""
    ai: AIConfig = AIConfig()
    ordering: OrderConfig = OrderConfig()
    reservations: ReservationConfig = ReservationConfig()
    notifications: NotificationConfig = NotificationConfig()
    branding: BrandingConfig = BrandingConfig()
    business: BusinessConfig = BusinessConfig()
    channels: ChannelConfig = ChannelConfig()
```

### How Config Flows Into the AI Agent

The dynamic system prompt is **built from config at runtime**:

```python
def build_system_prompt(config: RestaurantConfig, menu_summary: str) -> str:
    """Generates a unique system prompt for each restaurant."""

    prompt = f"""You are {config.ai.bot_name}, the AI assistant for {config.business.description or 'this restaurant'}.

## Your Personality
- Personality: {config.ai.personality}
- Tone: {config.ai.tone}
- Primary language: {config.ai.language}
- Supported languages: {', '.join(config.ai.supported_languages)}

## Greeting
When a customer starts a conversation, greet them with: "{config.ai.greeting_message}"

## What You Can Help With
{"- Taking food orders (dine-in, takeaway" + (", delivery" if config.ordering.delivery_enabled else "") + ")" if config.ordering.ordering_enabled else "- Ordering is currently disabled."}
{"- Table reservations (up to " + str(config.reservations.max_party_size) + " guests)" if config.reservations.reservations_enabled else "- Reservations are currently disabled."}
- Menu questions and recommendations
- Restaurant information and FAQs

## Business Rules
{"- Minimum order: " + str(config.ordering.minimum_order_amount) + " " + "USD" if config.ordering.minimum_order_amount > 0 else ""}
{"- Delivery fee: " + str(config.ordering.delivery_fee) if config.ordering.delivery_enabled else ""}
{"- Tax rate: " + str(float(config.ordering.tax_rate) * 100) + "%" if config.ordering.tax_rate > 0 else ""}
- Restaurant hours: [loaded from operating_hours table]

## Menu Categories
{menu_summary}

## Owner's Custom Instructions
{config.ai.custom_instructions}

{"## Upselling" if config.ai.upsell_enabled else ""}
{"Suggest complementary items when appropriate. " + config.ai.upsell_instructions if config.ai.upsell_enabled else ""}

## Important Rules
- ONLY recommend items from the menu tools. NEVER invent menu items.
- If a customer asks something outside your scope, say: "{config.ai.out_of_scope_message}"
- If you can't help, say: "{config.ai.fallback_message}"
- When the conversation ends naturally, say: "{config.ai.farewell_message}"
- Always be {config.ai.personality} and {config.ai.tone}.
"""
    return prompt
```

### Configuration Examples — Different Restaurants

**Example 1: Casual Burger Joint**
```json
{
  "ai": {
    "bot_name": "Burger Buddy",
    "personality": "casual and fun",
    "tone": "playful",
    "language": "en",
    "greeting_message": "Hey! Welcome to Burger Barn! Ready to build your dream burger?",
    "custom_instructions": "Always hype up our signature Barn Burger. Use casual language, emojis are OK.",
    "upsell_enabled": true,
    "upsell_instructions": "Always suggest adding bacon or upgrading to a combo with fries and shake."
  },
  "ordering": {
    "order_types": ["dine_in", "takeaway"],
    "delivery_enabled": false,
    "tax_rate": "0.08",
    "order_number_prefix": "BRG"
  },
  "reservations": {
    "reservations_enabled": false
  },
  "business": {
    "cuisine_type": ["American", "Burgers"],
    "price_range": "$",
    "description": "Burger Barn - the juiciest burgers in town since 2019"
  }
}
```

**Example 2: Fine Dining Italian Restaurant**
```json
{
  "ai": {
    "bot_name": "Concierge",
    "personality": "elegant and knowledgeable",
    "tone": "formal",
    "language": "en",
    "supported_languages": ["en", "it"],
    "greeting_message": "Good evening, welcome to La Dolce Vita. How may I assist you this evening?",
    "custom_instructions": "Recommend wine pairings with meals. Use formal language. Never use emojis or slang. Address guests as 'sir' or 'madam' when possible.",
    "upsell_enabled": true,
    "upsell_instructions": "Suggest wine pairings. Recommend our chef's tasting menu for special occasions."
  },
  "ordering": {
    "order_types": ["dine_in"],
    "delivery_enabled": false,
    "minimum_order_amount": "0.00",
    "tax_rate": "0.10",
    "tax_inclusive": true,
    "tip_enabled": true,
    "tip_options": [15, 18, 20, 25],
    "order_number_prefix": "LDV"
  },
  "reservations": {
    "reservations_enabled": true,
    "max_party_size": 12,
    "min_advance_hours": 4,
    "max_advance_days": 60,
    "default_duration_minutes": 120,
    "require_phone_for_reservation": true,
    "cancellation_policy": "Free cancellation up to 24 hours before. Late cancellations incur a $25/person fee."
  },
  "business": {
    "cuisine_type": ["Italian", "Fine Dining"],
    "price_range": "$$$$",
    "alcohol_served": true,
    "outdoor_seating": true,
    "description": "La Dolce Vita — authentic Italian fine dining since 1995"
  }
}
```

**Example 3: Pakistani/Indian Restaurant with WhatsApp Focus**
```json
{
  "ai": {
    "bot_name": "Karachi Kitchen Bot",
    "personality": "warm and welcoming",
    "tone": "friendly",
    "language": "en",
    "supported_languages": ["en", "ur"],
    "greeting_message": "Assalam o Alaikum! Welcome to Karachi Kitchen. What would you like to order today?",
    "custom_instructions": "Greet in Urdu if the customer writes in Urdu. Always mention today's special deal. Recommend our famous biryani to first-time customers.",
    "upsell_enabled": true,
    "upsell_instructions": "Suggest raita with biryani, naan with karahi, and mango lassi as a drink."
  },
  "ordering": {
    "order_types": ["dine_in", "takeaway"],
    "delivery_enabled": true,
    "delivery_radius_km": 10,
    "delivery_fee": "150.00",
    "delivery_minimum_order": "500.00",
    "minimum_order_amount": "200.00",
    "tax_rate": "0.16",
    "tax_inclusive": true,
    "order_number_prefix": "KK"
  },
  "reservations": {
    "reservations_enabled": true,
    "max_party_size": 30,
    "default_duration_minutes": 120
  },
  "business": {
    "cuisine_type": ["Pakistani", "Indian", "BBQ"],
    "price_range": "$$",
    "halal": true,
    "description": "Karachi Kitchen — authentic Pakistani cuisine, family-style dining"
  },
  "channels": {
    "whatsapp_enabled": true,
    "whatsapp_phone_number_id": "1234567890",
    "web_widget_enabled": true
  }
}
```

**Example 4: Cloud Kitchen (Delivery Only, No Dine-In)**
```json
{
  "ai": {
    "bot_name": "Order Bot",
    "personality": "efficient and quick",
    "tone": "direct",
    "language": "en",
    "greeting_message": "Hi! Ready to order? Check our menu or tell me what you're craving!",
    "custom_instructions": "Keep responses short. Focus on taking orders quickly. Always confirm delivery address.",
    "upsell_enabled": true,
    "upsell_instructions": "Suggest adding a dessert or drink to every order."
  },
  "ordering": {
    "order_types": ["delivery"],
    "delivery_enabled": true,
    "delivery_radius_km": 15,
    "delivery_fee": "3.99",
    "delivery_minimum_order": "15.00",
    "auto_confirm_orders": true,
    "order_number_prefix": "DLV"
  },
  "reservations": {
    "reservations_enabled": false
  },
  "business": {
    "cuisine_type": ["Multi-cuisine", "Cloud Kitchen"],
    "price_range": "$$"
  }
}
```

### Admin API for Configuration

Restaurant owners manage ALL config via REST API:

```
# Get full config
GET    /api/v1/restaurants/{id}/config

# Update entire config
PUT    /api/v1/restaurants/{id}/config

# Update specific section (partial update)
PATCH  /api/v1/restaurants/{id}/config/ai
PATCH  /api/v1/restaurants/{id}/config/ordering
PATCH  /api/v1/restaurants/{id}/config/reservations
PATCH  /api/v1/restaurants/{id}/config/notifications
PATCH  /api/v1/restaurants/{id}/config/branding
PATCH  /api/v1/restaurants/{id}/config/business
PATCH  /api/v1/restaurants/{id}/config/channels

# Reset section to defaults
DELETE /api/v1/restaurants/{id}/config/ai          # resets AI config to defaults

# Preview system prompt (see what the AI sees)
GET    /api/v1/restaurants/{id}/config/preview-prompt

# Test the bot with current config (owner can chat as a test customer)
POST   /api/v1/restaurants/{id}/config/test-chat
```

### Config Caching Strategy

```
1. Config loaded from DB on first request for a restaurant
2. Cached in memory (or Redis in production)
3. Cache TTL: 5 minutes (changes take effect within 5 min)
4. Cache invalidated immediately on PUT/PATCH to config API
5. System prompt rebuilt from config on each conversation start (not per message)
```

---

## Database Schema

### Tenant / Restaurant Layer

```
restaurants
    id: UUID (PK)
    name: str
    slug: str (unique)
    owner_id: UUID (FK -> users.id)
    timezone: str
    currency: str (default "USD")
    is_active: bool
    config: JSON              -- RestaurantConfig (the FULL config object above)
    created_at, updated_at

users
    id: UUID (PK)
    email: str (unique)
    password_hash: str
    role: enum (owner, manager, staff)
    restaurant_id: UUID (FK, nullable for superadmin)
    is_active: bool
    created_at, updated_at
```

### Menu Layer

```
menu_categories
    id: UUID (PK)
    restaurant_id: UUID (FK)
    name: str
    description: str | None
    sort_order: int
    is_active: bool

menu_items
    id: UUID (PK)
    restaurant_id: UUID (FK)
    category_id: UUID (FK)
    name: str
    description: str
    price: Decimal(10,2)
    image_url: str | None
    is_available: bool
    is_vegetarian: bool
    is_vegan: bool
    allergens: JSON  -- ["nuts", "dairy", ...]
    preparation_time_minutes: int | None
    sort_order: int
    created_at, updated_at

menu_item_modifiers
    id: UUID (PK)
    menu_item_id: UUID (FK)
    restaurant_id: UUID (FK)
    name: str  -- "Size", "Extra Toppings"
    options: JSON  -- [{"name": "Large", "price_delta": 2.00}, ...]
    is_required: bool
    max_selections: int
```

### Order Layer

```
customers
    id: UUID (PK)
    restaurant_id: UUID (FK)
    channel: str
    channel_user_id: str
    name: str | None
    phone: str | None
    email: str | None
    preferences: JSON
    created_at, updated_at
    UNIQUE(restaurant_id, channel, channel_user_id)

orders
    id: UUID (PK)
    restaurant_id: UUID (FK)
    customer_id: UUID (FK)
    order_number: str  -- "ORD-0042"
    status: enum (pending, confirmed, preparing, ready, delivered, cancelled)
    order_type: enum (dine_in, takeaway, delivery)
    table_number: str | None
    subtotal: Decimal(10,2)
    tax: Decimal(10,2)
    total: Decimal(10,2)
    special_instructions: str | None
    channel: str
    placed_at: datetime
    estimated_ready_at: datetime | None
    completed_at: datetime | None
    created_at, updated_at

order_items
    id: UUID (PK)
    order_id: UUID (FK)
    menu_item_id: UUID (FK)
    quantity: int
    unit_price: Decimal(10,2)
    modifiers: JSON  -- selected modifiers snapshot
    item_total: Decimal(10,2)
    special_instructions: str | None
```

### Reservation Layer

```
tables
    id: UUID (PK)
    restaurant_id: UUID (FK)
    table_number: str
    capacity: int
    is_active: bool

reservations
    id: UUID (PK)
    restaurant_id: UUID (FK)
    customer_id: UUID (FK)
    table_id: UUID (FK, nullable)
    party_size: int
    reservation_date: date
    reservation_time: time
    duration_minutes: int (default 90)
    status: enum (pending, confirmed, seated, completed, cancelled, no_show)
    special_requests: str | None
    channel: str
    created_at, updated_at
```

### Operating Hours & FAQ

```
operating_hours
    id: UUID (PK)
    restaurant_id: UUID (FK)
    day_of_week: int (0=Monday, 6=Sunday)
    open_time: time
    close_time: time
    is_closed: bool

faqs
    id: UUID (PK)
    restaurant_id: UUID (FK)
    question: str
    answer: str
    sort_order: int
    is_active: bool
```

### Analytics / Logging

```
conversation_logs
    id: UUID (PK)
    restaurant_id: UUID (FK)
    session_id: str
    customer_id: UUID (FK, nullable)
    channel: str
    role: enum (user, assistant, tool_call, tool_result)
    content: text
    token_count: int | None
    created_at: datetime
```

### Cross-Database Compatibility Notes
- `Decimal(10,2)` for prices (not float)
- `UUID` via SQLAlchemy's `Uuid` type adapter (works on all DBs)
- JSON columns: native on PostgreSQL, JSON1 on SQLite, JSON type on MySQL
- Enums stored as strings for portability, validated at Pydantic layer
- Alembic `batch_alter_table` for SQLite migration compatibility

---

## Project Structure

```
restaurant-bot/
├── pyproject.toml                     # All dependencies
├── alembic.ini                        # DB migration config
├── Dockerfile                         # Multi-stage production build
├── docker-compose.yml                 # Dev: app + postgres + redis
├── docker-compose.prod.yml            # Prod overrides
├── .env.example                       # Template (only LLM_API_KEY required)
├── Makefile                           # make dev, make migrate, make test, make seed
├── README.md
│
├── alembic/
│   ├── env.py                         # Async-aware Alembic environment
│   └── versions/                      # Migration files
│
├── src/
│   └── restaurant_bot/
│       ├── __init__.py
│       ├── main.py                    # FastAPI app factory
│       ├── config.py                  # Pydantic Settings (env vars)
│       ├── dependencies.py            # FastAPI dependency injection
│       │
│       ├── db/
│       │   ├── __init__.py
│       │   ├── engine.py              # create_async_engine, session factory
│       │   ├── base.py                # DeclarativeBase, TenantMixin, TenantQuery
│       │   └── models/
│       │       ├── __init__.py        # Import all for Alembic discovery
│       │       ├── restaurant.py      # Restaurant, User, OperatingHours
│       │       ├── menu.py            # MenuCategory, MenuItem, Modifier
│       │       ├── order.py           # Order, OrderItem, Customer
│       │       ├── reservation.py     # Table, Reservation
│       │       └── conversation.py    # ConversationLog, FAQ
│       │
│       ├── schemas/                   # Pydantic request/response models
│       │   ├── __init__.py
│       │   ├── menu.py
│       │   ├── order.py
│       │   ├── reservation.py
│       │   ├── restaurant.py
│       │   ├── chat.py               # ChatRequest, ChatResponse
│       │   └── config.py             # RestaurantConfig, AIConfig, OrderConfig, etc.
│       │
│       ├── channels/                  # Channel adapters (THE agnostic layer)
│       │   ├── __init__.py
│       │   ├── base.py               # Abstract ChannelAdapter, IncomingMessage, OutgoingMessage
│       │   ├── rest_api.py           # REST API adapter (Day 1)
│       │   ├── whatsapp.py           # WhatsApp adapter (stub → implement in Phase 5)
│       │   └── telegram.py           # Telegram adapter (stub)
│       │
│       ├── agent/                     # AI Agent (Pydantic AI)
│       │   ├── __init__.py
│       │   ├── core.py               # Agent definition, system prompt builder
│       │   ├── deps.py               # RestaurantBotDeps dataclass
│       │   ├── tools/
│       │   │   ├── __init__.py
│       │   │   ├── menu_tools.py     # get_menu, search_menu_items
│       │   │   ├── order_tools.py    # add_to_cart, place_order, get_order_status
│       │   │   ├── reservation_tools.py  # check_availability, make/cancel reservation
│       │   │   └── info_tools.py     # get_restaurant_info, get_faq_answer
│       │   └── prompts/
│       │       └── system.py         # Dynamic system prompt builder
│       │
│       ├── services/                  # Business logic (decoupled from HTTP & AI)
│       │   ├── __init__.py
│       │   ├── menu_service.py
│       │   ├── order_service.py
│       │   ├── reservation_service.py
│       │   ├── customer_service.py
│       │   ├── config_service.py      # Load, cache, validate, update restaurant config
│       │   └── analytics_service.py
│       │
│       ├── api/                       # FastAPI routers
│       │   ├── __init__.py
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── router.py          # Aggregates all v1 routers
│       │       ├── chat.py            # POST /chat endpoint
│       │       ├── menu.py            # Menu CRUD (admin)
│       │       ├── orders.py          # Order management (admin)
│       │       ├── reservations.py    # Reservation endpoints (admin)
│       │       ├── restaurants.py     # Restaurant CRUD (superadmin)
│       │       ├── config.py          # GET/PUT/PATCH config, preview prompt, test chat
│       │       ├── analytics.py       # Analytics endpoints
│       │       ├── auth.py            # Login, register, token refresh
│       │       └── webhooks.py        # Channel webhook receivers
│       │
│       ├── session/                   # Conversation session management
│       │   ├── __init__.py
│       │   ├── base.py               # Abstract SessionStore
│       │   ├── memory.py             # InMemorySessionStore
│       │   ├── redis_store.py        # RedisSessionStore
│       │   ├── database.py           # DatabaseSessionStore (fallback)
│       │   └── cart.py               # Cart model and operations
│       │
│       ├── auth/                      # Authentication & authorization
│       │   ├── __init__.py
│       │   ├── jwt.py                # JWT token creation/verification
│       │   ├── password.py           # bcrypt hashing
│       │   └── permissions.py        # Role-based access control
│       │
│       ├── middleware/
│       │   ├── __init__.py
│       │   ├── tenant.py             # Tenant resolution middleware
│       │   ├── rate_limit.py         # Per-tenant rate limiting
│       │   └── logging.py            # Request/response logging
│       │
│       └── utils/
│           ├── __init__.py
│           ├── order_number.py       # Sequential order number generator
│           ├── time.py               # Timezone-aware helpers
│           └── pricing.py            # Tax calculation, totals
│
├── tests/
│   ├── conftest.py                   # Fixtures: test DB, test client, mock agent
│   ├── test_agent/
│   │   ├── test_menu_tools.py
│   │   ├── test_order_tools.py
│   │   └── test_reservation_tools.py
│   ├── test_api/
│   │   ├── test_chat.py
│   │   ├── test_menu_crud.py
│   │   └── test_orders.py
│   ├── test_channels/
│   │   ├── test_rest_adapter.py
│   │   └── test_whatsapp_adapter.py
│   └── test_services/
│       ├── test_order_service.py
│       └── test_reservation_service.py
│
└── scripts/
    ├── seed_demo.py                  # Seeds demo restaurant with realistic menu
    └── create_superadmin.py          # CLI to create first admin user
```

---

## Data Flow: Customer Sends a Chat Message

```
1. POST /api/v1/restaurants/{restaurant_id}/chat
   Body: {"message": "What pizzas do you have?", "session_id": "abc123"}

2. api/v1/chat.py:
   - Validates request (Pydantic schema)
   - Resolves restaurant from path param
   - Gets/creates session from SessionStore

3. channels/rest_api.py:
   - normalize() wraps HTTP body into IncomingMessage

4. agent/core.py:
   - Builds RestaurantBotDeps (db session, restaurant_id, session, cart)
   - Loads dynamic system prompt from DB
   - Calls restaurant_agent.run(message, deps=deps, message_history=session.history)

5. Pydantic AI decides to call tool: search_menu_items(ctx, query="pizza")

6. agent/tools/menu_tools.py:
   - Queries menu_items WHERE restaurant_id AND name LIKE '%pizza%' AND is_available
   - Returns structured list with prices

7. LLM formats response with menu data

8. agent/core.py returns AgentResponse
   - Saves conversation turn to session
   - Logs to conversation_logs table

9. channels/rest_api.py:
   - render() formats into HTTP JSON response

10. Response: {"reply": "We have three pizzas: ...", "suggestions": ["Add to cart", "Full menu"]}
```

---

## When WhatsApp is Added (Phase 5)

Only new code needed:

```python
# channels/whatsapp.py — ONE FILE, ~100 lines
class WhatsAppAdapter(ChannelAdapter):
    def normalize(self, payload: dict) -> IncomingMessage:
        msg = payload["entry"][0]["changes"][0]["value"]["messages"][0]
        return IncomingMessage(
            channel="whatsapp",
            sender_id=msg["from"],
            restaurant_id=self.resolve_restaurant(payload),
            text=msg.get("text", {}).get("body"),
            ...
        )

    def render(self, message: OutgoingMessage) -> dict:
        # Convert buttons to WhatsApp interactive format
        ...

    async def send(self, rendered: dict):
        # POST to Meta Graph API
        ...
```

Plus one webhook route in `api/v1/webhooks.py`. **Zero changes to agent, tools, services, or database.**

---

## Session Management

```python
@dataclass
class ConversationSession:
    session_id: str
    restaurant_id: uuid.UUID
    customer_id: uuid.UUID | None
    channel: str
    sender_id: str
    cart: Cart
    conversation_history: list[Message]
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime  # 30 min inactivity, cart persists 24h
```

**Pluggable backends:**
- `InMemorySessionStore` — dev, single process
- `RedisSessionStore` — production, distributed
- `DatabaseSessionStore` — fallback, no Redis needed

---

## Build Phases (Detailed)

### Phase 1: Foundation + Menu + Chat + Config (Week 1) — COMPLETED
- [x] Project scaffolding (pyproject.toml, config, Makefile, Docker)
- [x] Database models + initial Alembic migration
- [x] **RestaurantConfig schema** (all Pydantic config models with defaults)
- [x] **Config service** (load, cache, validate, update config from DB)
- [x] **Config API** (GET/PUT/PATCH config, preview prompt, test chat)
- [x] Menu CRUD API (admin endpoints for categories & items)
- [x] AI Agent core with menu tools + **dynamic system prompt from config**
- [x] Chat endpoint via REST API adapter
- [x] In-memory session store
- [x] Seed script with demo restaurant data (including sample configs)
- **Deliverable**: Working chatbot that behaves differently per restaurant config

### Phase 2: Ordering System (Week 2) — COMPLETED
- [x] Cart system (session-based add/remove/modify/update quantity + modifier support)
- [x] Order placement (cart → order conversion, order number generation, delivery address, estimated ready time)
- [x] Order tracking (status queries, order history per customer via get_my_orders tool)
- [x] Order management API (admin: list with date filter, status update, cancel with reason, stats summary)
- **Deliverable**: Full conversational ordering flow

### Phase 3: Reservations + Auth (Week 3) — COMPLETED
- [x] Table management CRUD (list, create, update, delete API endpoints)
- [x] Reservation system (time-overlap detection, time slot generation, availability check endpoint, admin create)
- [x] JWT authentication for admin endpoints (built in Phase 1)
- [x] Role-based access control (owner, manager, staff, superadmin guards)
- [x] Conversation logging wired into chat flow
- **Deliverable**: Complete core product

### Phase 4: Production Readiness (Week 4) — COMPLETED
- [x] Redis session store implementation (with JSON serialization, TTL expiry)
- [x] Analytics service (popular items, order status breakdown, channel stats, full dashboard)
- [x] Conversation logging (full audit trail — wired in Phase 3)
- [x] Rate limiting (per-tenant, per-customer, 60 RPM + burst protection)
- [x] Docker production setup (docker-compose.prod.yml with Gunicorn, health checks, volumes)
- [x] Health check endpoints (/health + /ready with DB connectivity check)
- [x] wa.me link generator + QR code generator for web chat & WhatsApp
- [x] WhatsApp setup guide in admin panel
- **Deliverable**: Deployable SaaS product

### Phase 5: WhatsApp Integration (Week 5) — COMPLETED
- [x] WhatsApp adapter (normalize + render + send via Meta Graph API)
- [x] Webhook endpoint for Meta Cloud API (GET verify + POST receive)
- [x] Phone-to-restaurant mapping (lookup by phone_number_id)
- [x] WhatsApp interactive messages (buttons for <=3, list for >3)
- [x] Plan/tier system (free = web only, pro = web + WhatsApp)
- [x] Channels tab in admin panel (share link, embed code, WhatsApp config)
- **Deliverable**: WhatsApp-ready product with plan gating

---

## Configuration (Plug-and-Play)

### .env.example

```bash
# === REQUIRED (minimum to start) ===
LLM_API_KEY=sk-ant-your-key-here

# === OPTIONAL (sensible defaults) ===
DATABASE_URL=sqlite+aiosqlite:///./restaurant_bot.db
LLM_PROVIDER=anthropic          # or "openai", "google"
LLM_MODEL=claude-sonnet-4-20250514
SECRET_KEY=auto-generated-on-first-run
SESSION_STORE=memory             # or "redis", "database"
REDIS_URL=redis://localhost:6379
LOG_LEVEL=INFO
CORS_ORIGINS=["*"]
DEFAULT_CURRENCY=USD
DEFAULT_TIMEZONE=UTC
```

### Getting Started

```bash
# Option 1: Local development
git clone <repo> && cd restaurant-bot
cp .env.example .env           # Set LLM_API_KEY
make dev                       # uv sync + migrate + start server

# Option 2: Docker (zero setup)
docker compose up              # SQLite + in-memory, ready to chat

# Option 3: Production
DATABASE_URL=postgresql+asyncpg://user:pass@host/db \
SESSION_STORE=redis \
REDIS_URL=redis://host:6379 \
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## Key Dependencies

```toml
[project]
name = "restaurant-bot"
requires-python = ">=3.12"
dependencies = [
    # Core
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "gunicorn>=23.0",

    # AI Agent
    "pydantic-ai[anthropic,openai]>=0.2",

    # Database
    "sqlalchemy[asyncio]>=2.0.51",
    "alembic>=1.18",
    "aiosqlite>=0.20",          # SQLite async driver
    "asyncpg>=0.30",            # PostgreSQL async driver
    "aiomysql>=0.2",            # MySQL async driver (optional)

    # Auth
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7",
    "python-multipart>=0.0.9",

    # Session & Cache
    "redis>=5.0",

    # Utilities
    "pydantic-settings>=2.5",
    "httpx>=0.27",
    "jinja2>=3.1",
    "structlog>=24.4",
]
```

---

## Deployment Options

| Platform | Command | Cost |
|----------|---------|------|
| Railway | `railway up` | $5/mo |
| Render | Connect GitHub | $7/mo |
| Fly.io | `fly launch` | $5/mo |
| Any VPS | `docker compose up -d` | $5-10/mo |
| AWS ECS | Terraform module | ~$20/mo |

---

## Challenges & Mitigations

| Challenge | Mitigation |
|-----------|-----------|
| LLM hallucinating menu items | Tools return actual DB data. System prompt: "Only recommend items from tools." |
| Cart lost on restart | Redis in prod. DB fallback for carts >5 min old. |
| SQLite concurrent writes | WAL mode in dev. PostgreSQL in prod. |
| WhatsApp rate limits | Queue outbound messages. 80 msg/sec limit. Exponential backoff. |
| Multi-tenant data leaks | Every query through TenantQuery.scoped(). Integration tests verify isolation. |
| LLM provider outages | Pydantic AI model-agnostic: fallback from Claude → GPT. |
| Order race conditions | DB constraints on order numbers. Optimistic locking on status. |

---

## Testing Strategy

- **Unit tests**: Tool functions with mock DB sessions. Pydantic AI `TestModel` for deterministic testing.
- **Integration tests**: Full request cycle with SQLite in-memory DB.
- **Agent tests**: Scripted conversations verifying correct tool calls.
- **Multi-tenant tests**: Two restaurants, verify zero data leakage.

---

## Verification Checklist

- [ ] `make dev` starts without errors
- [ ] Seed script populates demo restaurant with sample config
- [ ] `GET /config` returns full RestaurantConfig with defaults
- [ ] `PATCH /config/ai` updates bot personality — next chat uses new personality
- [ ] `GET /config/preview-prompt` shows the dynamic system prompt
- [ ] `POST /chat` with "show me the menu" returns real menu items
- [ ] Same chat endpoint behaves differently for two restaurants with different configs
- [ ] Full order flow: browse → add to cart → place order → check status
- [ ] Order flow respects OrderConfig (min order, tax, delivery rules)
- [ ] Reservation flow: check availability → book → confirm
- [ ] Reservation flow respects ReservationConfig (max party size, advance booking)
- [ ] Switch DATABASE_URL to PostgreSQL — everything works
- [ ] `pytest` — all tests pass
- [ ] Docker build + run works

---

## Pricing Model (SaaS)

| Tier | Price | Limits |
|------|-------|--------|
| Starter | $39/mo | 1 restaurant, 1 channel, 500 conversations/mo |
| Growth | $69/mo | 1 restaurant, 3 channels, 2000 conversations/mo |
| Chain | $99/mo + $29/location | Unlimited restaurants, all channels, unlimited |

LLM cost per conversation: ~$0.003-0.01. At $39/mo with 500 conversations = ~$5 LLM cost. Healthy margins.

---

## Critical Files (Implementation Priority)

1. `src/restaurant_bot/schemas/config.py` — RestaurantConfig with all sub-configs (THE configurability layer)
2. `src/restaurant_bot/services/config_service.py` — load, cache, validate, update per-restaurant config
3. `src/restaurant_bot/config.py` — app-level settings (env vars, plug-and-play)
4. `src/restaurant_bot/channels/base.py` — channel-agnostic contract
5. `src/restaurant_bot/db/base.py` — multi-tenancy foundation
6. `src/restaurant_bot/agent/core.py` — AI brain + dynamic prompt builder (reads config)
7. `src/restaurant_bot/agent/tools/order_tools.py` — revenue path (ordering, respects OrderConfig rules)
8. `src/restaurant_bot/api/v1/config.py` — config CRUD API for restaurant owners

---

> **This plan is the single source of truth. Every implementation decision follows this document.**
> **Every restaurant is unique. The config system makes the bot unique for each one — zero code changes.**
