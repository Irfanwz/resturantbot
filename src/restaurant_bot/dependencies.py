from restaurant_bot.db.engine import get_db
from restaurant_bot.session.memory import InMemorySessionStore

# Global session store instance
session_store = InMemorySessionStore(ttl_minutes=30)
