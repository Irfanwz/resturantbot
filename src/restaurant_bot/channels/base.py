from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Button:
    label: str
    value: str


@dataclass
class Media:
    type: str  # "image", "document"
    url: str
    caption: str | None = None


@dataclass
class IncomingMessage:
    channel: str
    sender_id: str
    restaurant_id: str
    text: str | None = None
    media_url: str | None = None
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OutgoingMessage:
    recipient_id: str
    text: str
    buttons: list[Button] | None = None
    media: list[Media] | None = None
    metadata: dict = field(default_factory=dict)


class ChannelAdapter(ABC):
    """Base class for all channel adapters. Each channel implements normalize and render."""

    @abstractmethod
    def normalize(self, raw_payload: dict) -> IncomingMessage:
        """Convert channel-specific payload to canonical IncomingMessage."""
        ...

    @abstractmethod
    def render(self, message: OutgoingMessage) -> dict:
        """Convert canonical OutgoingMessage to channel-specific response."""
        ...

    async def send(self, rendered: dict) -> None:
        """Send the rendered message via the channel. Override for push channels (WhatsApp, Telegram)."""
        pass  # REST API doesn't need this — it returns the response directly
