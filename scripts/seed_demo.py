"""
Seed script to create a demo restaurant with menu data.
Run: python -m scripts.seed_demo
"""
import asyncio
import uuid
from datetime import time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.engine import async_session_factory, engine
from restaurant_bot.db.base import Base
from restaurant_bot.db.models.restaurant import Restaurant, User, OperatingHours
from restaurant_bot.db.models.menu import MenuCategory, MenuItem, MenuItemModifier
from restaurant_bot.db.models.reservation import Table
from restaurant_bot.db.models.conversation import FAQ, AutoReply
from restaurant_bot.auth.password import hash_password
from restaurant_bot.schemas.config import RestaurantConfig, AIConfig, OrderConfig, ReservationConfig, BusinessConfig


async def seed():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        # Check if already seeded
        from sqlalchemy import select
        existing = await db.execute(select(Restaurant).where(Restaurant.slug == "demo-restaurant"))
        if existing.scalar_one_or_none():
            print("Demo restaurant already exists. Skipping seed.")
            return

        # Create restaurant config
        config = RestaurantConfig(
            ai=AIConfig(
                bot_name="FoodieBot",
                personality="friendly and enthusiastic about food",
                tone="warm",
                greeting_message="Hey there! Welcome to The Golden Fork! I'm FoodieBot, and I'm here to help you with our menu, take your order, or book a table. What can I do for you?",
                farewell_message="Thanks for visiting The Golden Fork! Enjoy your meal! See you next time!",
                custom_instructions="Always recommend our signature Truffle Burger when someone asks for suggestions. Mention daily specials if relevant.",
                upsell_enabled=True,
                upsell_instructions="Suggest adding a drink or dessert to every order. Recommend upgrading to a combo when available.",
            ),
            ordering=OrderConfig(
                ordering_enabled=True,
                order_types=["dine_in", "takeaway"],
                delivery_enabled=True,
                delivery_radius_km=10,
                delivery_fee=Decimal("3.99"),
                delivery_minimum_order=Decimal("15.00"),
                minimum_order_amount=Decimal("5.00"),
                tax_rate=Decimal("0.08"),
                order_number_prefix="GF",
            ),
            reservations=ReservationConfig(
                reservations_enabled=True,
                max_party_size=12,
                min_advance_hours=2,
                max_advance_days=30,
            ),
            business=BusinessConfig(
                address="123 Food Street, Flavor Town, FT 12345",
                phone="+1-555-FOOD-123",
                email="hello@goldenfork.com",
                cuisine_type=["American", "Burgers", "Italian", "Desserts"],
                price_range="$$",
                parking_available=True,
                wifi_available=True,
                outdoor_seating=True,
                description="The Golden Fork — where every bite is an adventure! Serving the best burgers, pasta, and desserts since 2020.",
            ),
        )

        # Create restaurant
        restaurant = Restaurant(
            name="The Golden Fork",
            slug="demo-restaurant",
            timezone="America/New_York",
            currency="USD",
            plan="pro",
            config=config.model_dump(mode="json"),
        )
        db.add(restaurant)
        await db.flush()
        rid = restaurant.id

        # Create owner user
        user = User(
            email="admin@goldenfork.com",
            password_hash=hash_password("admin123"),
            full_name="Demo Owner",
            role="owner",
            restaurant_id=rid,
        )
        db.add(user)

        # Operating hours
        for day in range(7):
            is_closed = day == 0  # Closed Monday
            db.add(OperatingHours(
                restaurant_id=rid,
                day_of_week=day,
                open_time=time(11, 0),
                close_time=time(22, 0),
                is_closed=is_closed,
            ))

        # Tables
        for i in range(1, 11):
            capacity = 2 if i <= 4 else (4 if i <= 7 else 6)
            db.add(Table(restaurant_id=rid, table_number=f"T{i}", capacity=capacity))

        # Menu Categories and Items
        # Starters
        starters = MenuCategory(restaurant_id=rid, name="Starters", description="Begin your journey", sort_order=1)
        db.add(starters)
        await db.flush()

        starters_items = [
            ("Garlic Bread", "Crispy bread with garlic butter and herbs", Decimal("6.99"), False, True),
            ("Mozzarella Sticks", "Golden fried mozzarella with marinara sauce", Decimal("8.99"), False, True),
            ("Caesar Salad", "Romaine lettuce, croutons, parmesan, caesar dressing", Decimal("9.99"), True, True),
            ("Soup of the Day", "Chef's daily creation — ask your server!", Decimal("5.99"), True, True),
        ]
        for name, desc, price, is_veg, available in starters_items:
            db.add(MenuItem(restaurant_id=rid, category_id=starters.id, name=name, description=desc, price=price, is_vegetarian=is_veg, is_available=available, sort_order=starters_items.index((name, desc, price, is_veg, available))))

        # Burgers
        burgers = MenuCategory(restaurant_id=rid, name="Burgers", description="Our famous handcrafted burgers", sort_order=2)
        db.add(burgers)
        await db.flush()

        burgers_items = [
            ("Classic Burger", "Beef patty, lettuce, tomato, onion, special sauce", Decimal("12.99")),
            ("Truffle Burger", "Signature! Angus beef, truffle aioli, caramelized onions, gruyere", Decimal("16.99")),
            ("BBQ Bacon Burger", "Beef patty, crispy bacon, cheddar, BBQ sauce, onion rings", Decimal("14.99")),
            ("Veggie Burger", "Plant-based patty, avocado, sprouts, vegan aioli", Decimal("13.99")),
            ("Chicken Burger", "Grilled chicken breast, lettuce, mayo, pickles", Decimal("11.99")),
        ]
        for i, (name, desc, price) in enumerate(burgers_items):
            item = MenuItem(restaurant_id=rid, category_id=burgers.id, name=name, description=desc, price=price, is_vegetarian=name == "Veggie Burger", sort_order=i)
            db.add(item)
            await db.flush()
            # Add size modifier to burgers
            db.add(MenuItemModifier(
                restaurant_id=rid, menu_item_id=item.id, name="Size",
                options=[{"name": "Regular", "price_delta": 0}, {"name": "Double", "price_delta": 4.00}],
                is_required=False, max_selections=1,
            ))

        # Pasta
        pasta = MenuCategory(restaurant_id=rid, name="Pasta", description="Fresh Italian pasta", sort_order=3)
        db.add(pasta)
        await db.flush()

        pasta_items = [
            ("Spaghetti Bolognese", "Classic meat sauce with parmesan", Decimal("14.99")),
            ("Fettuccine Alfredo", "Creamy parmesan sauce with fettuccine", Decimal("13.99")),
            ("Penne Arrabbiata", "Spicy tomato sauce with garlic and chili", Decimal("12.99")),
        ]
        for i, (name, desc, price) in enumerate(pasta_items):
            db.add(MenuItem(restaurant_id=rid, category_id=pasta.id, name=name, description=desc, price=price, is_vegetarian=name == "Penne Arrabbiata", sort_order=i))

        # Drinks
        drinks = MenuCategory(restaurant_id=rid, name="Drinks", description="Refresh yourself", sort_order=4)
        db.add(drinks)
        await db.flush()

        drinks_items = [
            ("Coca-Cola", "330ml can", Decimal("2.99")),
            ("Fresh Lemonade", "Freshly squeezed with mint", Decimal("4.99")),
            ("Iced Tea", "Peach or lemon", Decimal("3.99")),
            ("Milkshake", "Chocolate, vanilla, or strawberry", Decimal("6.99")),
        ]
        for i, (name, desc, price) in enumerate(drinks_items):
            db.add(MenuItem(restaurant_id=rid, category_id=drinks.id, name=name, description=desc, price=price, is_vegetarian=True, sort_order=i))

        # Desserts
        desserts = MenuCategory(restaurant_id=rid, name="Desserts", description="Sweet endings", sort_order=5)
        db.add(desserts)
        await db.flush()

        desserts_items = [
            ("Chocolate Lava Cake", "Warm chocolate cake with molten center, vanilla ice cream", Decimal("8.99")),
            ("New York Cheesecake", "Classic creamy cheesecake with berry compote", Decimal("7.99")),
            ("Tiramisu", "Italian coffee-flavored dessert with mascarpone", Decimal("8.99")),
        ]
        for i, (name, desc, price) in enumerate(desserts_items):
            db.add(MenuItem(restaurant_id=rid, category_id=desserts.id, name=name, description=desc, price=price, is_vegetarian=True, sort_order=i))

        # FAQs
        faqs = [
            ("Do you have parking?", "Yes! We have free parking for all customers right next to the restaurant."),
            ("Is the food halal?", "Please ask our staff about specific menu items as ingredients may vary."),
            ("Do you cater for events?", "Yes! We offer catering for events of 20+ people. Contact us at hello@goldenfork.com for details."),
            ("Do you have gluten-free options?", "Yes, several items on our menu are gluten-free. Our salads, the veggie burger (without bun), and grilled chicken options are all gluten-free."),
            ("What's your cancellation policy?", "Free cancellation up to 2 hours before your reservation time."),
        ]
        for i, (q, a) in enumerate(faqs):
            db.add(FAQ(restaurant_id=rid, question=q, answer=a, sort_order=i))

        # Default Auto-Replies (FREE responses - no LLM cost)
        default_auto_replies = [
            # Greetings (priority 10 - checked first)
            AutoReply(
                restaurant_id=rid,
                trigger_patterns=["hi", "hello", "hey", "hola", "greetings", "good morning", "good afternoon", "good evening"],
                response="{greeting_message}\n\nI can help you with:\n- Viewing our menu\n- Placing an order\n- Making a reservation\n- Restaurant info\n\nWhat would you like to do?",
                category="greeting",
                priority=10,
                match_type="keyword",
            ),
            # Farewells
            AutoReply(
                restaurant_id=rid,
                trigger_patterns=["bye", "goodbye", "see you", "later", "good night", "take care"],
                response="{farewell_message}",
                category="farewell",
                priority=10,
                match_type="keyword",
            ),
            # Thanks
            AutoReply(
                restaurant_id=rid,
                trigger_patterns=["thank", "thanks", "thank you", "thx", "appreciate"],
                response="You're welcome! Is there anything else I can help you with? \U0001f60a",
                category="thanks",
                priority=10,
                match_type="keyword",
            ),
            # Address / Location
            AutoReply(
                restaurant_id=rid,
                trigger_patterns=["where are you", "address", "location", "directions", "where is", "how to reach", "find you"],
                response="\U0001f4cd We're located at: {address}\n\U0001f4de Phone: {phone}\n\U0001f4e7 Email: {email}\n\nWe'd love to see you!",
                category="info",
                priority=5,
                match_type="keyword",
            ),
            # Contact
            AutoReply(
                restaurant_id=rid,
                trigger_patterns=["phone", "call", "contact", "number"],
                response="You can reach us at:\n\U0001f4de Phone: {phone}\n\U0001f4e7 Email: {email}",
                category="info",
                priority=5,
                match_type="keyword",
            ),
            # Bot identity
            AutoReply(
                restaurant_id=rid,
                trigger_patterns=["who are you", "what are you", "your name"],
                response="I'm {bot_name}, the AI assistant for {restaurant_name}! I can help you browse our menu, place orders, and make table reservations. How can I help?",
                category="info",
                priority=5,
                match_type="keyword",
            ),
            # Help
            AutoReply(
                restaurant_id=rid,
                trigger_patterns=["help", "what can you do", "how does this work"],
                response="I'm {bot_name} and I can help you with:\n\n\U0001f37d\ufe0f **Menu** \u2014 Ask me about our dishes, prices, or dietary options\n\U0001f6d2 **Order** \u2014 Add items to cart and place orders\n\U0001f4c5 **Reservations** \u2014 Book a table\n\u2139\ufe0f **Info** \u2014 Hours, location, contact details\n\nJust type what you need!",
                category="info",
                priority=8,
                match_type="keyword",
            ),
            # Yes/OK acknowledgment
            AutoReply(
                restaurant_id=rid,
                trigger_patterns=["ok", "okay", "sure", "alright", "got it", "understood"],
                response="Great! What would you like to do next? I can show you the menu, take an order, or help with a reservation.",
                category="acknowledgment",
                priority=3,
                match_type="exact",
            ),
        ]
        for ar in default_auto_replies:
            db.add(ar)

        await db.commit()
        print(f"Demo restaurant created successfully!")
        print(f"  Restaurant ID: {rid}")
        print(f"  Name: The Golden Fork")
        print(f"  Slug: demo-restaurant")
        print(f"  Admin email: admin@goldenfork.com")
        print(f"  Admin password: admin123")
        print(f"  Menu items: 19 items across 5 categories")
        print(f"  Tables: 10 (2-seat: 4, 4-seat: 3, 6-seat: 3)")
        print(f"  FAQs: {len(faqs)}")


if __name__ == "__main__":
    asyncio.run(seed())
