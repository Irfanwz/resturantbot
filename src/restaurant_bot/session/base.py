import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from restaurant_bot.session.cart import Cart


@dataclass
class ConversationSession:
    session_id: str
    restaurant_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    channel: str = "rest_api"
    sender_id: str = "anonymous"
    cart: Cart = field(default_factory=Cart)
    conversation_history: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_message(self, role: str, content: str) -> None:
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.last_active_at = datetime.now(timezone.utc)


class SessionStore(ABC):
    @abstractmethod
    async def get(self, session_id: str) -> ConversationSession | None:
        ...

    @abstractmethod
    async def save(self, session: ConversationSession) -> None:
        ...

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        ...
