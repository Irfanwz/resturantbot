import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, Text, ForeignKey, Uuid, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from restaurant_bot.db.base import Base, TenantMixin

class ConversationLog(Base, TenantMixin):
    __tablename__ = "conversation_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(255), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20))  # user, assistant, tool_call, tool_result
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

class FAQ(Base, TenantMixin):
    __tablename__ = "faqs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class AutoReply(Base, TenantMixin):
    """Pattern-based auto-replies that skip the LLM. Owners can CRUD these."""
    __tablename__ = "auto_replies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    trigger_patterns: Mapped[dict] = mapped_column(JSON, default=list)  # ["hi", "hello", "hey", "greetings"]
    response: Mapped[str] = mapped_column(Text)  # "Welcome to {restaurant_name}! {greeting_message}"
    category: Mapped[str] = mapped_column(String(50), default="greeting")  # greeting, farewell, thanks, info, custom
    priority: Mapped[int] = mapped_column(Integer, default=0)  # higher = checked first
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    match_type: Mapped[str] = mapped_column(String(20), default="keyword")  # "keyword" (any word matches) or "exact" (full message matches)
