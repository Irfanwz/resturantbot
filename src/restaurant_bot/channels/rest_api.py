from restaurant_bot.channels.base import ChannelAdapter, IncomingMessage, OutgoingMessage


class RestAPIAdapter(ChannelAdapter):
    """Adapter for the REST API channel. Used for web chat widgets and API clients."""

    def normalize(self, raw_payload: dict) -> IncomingMessage:
        return IncomingMessage(
            channel="rest_api",
            sender_id=raw_payload.get("sender_id", "anonymous"),
            restaurant_id=raw_payload["restaurant_id"],
            text=raw_payload.get("message"),
            media_url=raw_payload.get("media_url"),
            metadata=raw_payload.get("metadata", {}),
        )

    def render(self, message: OutgoingMessage) -> dict:
        response = {
            "reply": message.text,
            "recipient_id": message.recipient_id,
        }
        if message.buttons:
            response["suggestions"] = [
                {"label": b.label, "value": b.value} for b in message.buttons
            ]
        if message.media:
            response["media"] = [
                {"type": m.type, "url": m.url, "caption": m.caption} for m in message.media
            ]
        return response
