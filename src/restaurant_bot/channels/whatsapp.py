import httpx
from restaurant_bot.channels.base import ChannelAdapter, IncomingMessage, OutgoingMessage, Button


class WhatsAppAdapter(ChannelAdapter):
    """
    WhatsApp Cloud API adapter.
    Normalizes Meta webhook payloads to canonical messages,
    renders responses to WhatsApp interactive format,
    and sends via Meta Graph API.
    """

    def normalize(self, raw_payload: dict) -> IncomingMessage | None:
        """Parse Meta's webhook payload into a canonical IncomingMessage."""
        try:
            entry = raw_payload.get("entry", [])
            if not entry:
                return None

            changes = entry[0].get("changes", [])
            if not changes:
                return None

            value = changes[0].get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None

            msg = messages[0]
            contacts = value.get("contacts", [])
            sender_name = contacts[0].get("profile", {}).get("name", "") if contacts else ""

            # Extract text from different message types
            text = None
            if msg.get("type") == "text":
                text = msg["text"]["body"]
            elif msg.get("type") == "interactive":
                interactive = msg.get("interactive", {})
                if interactive.get("type") == "button_reply":
                    text = interactive["button_reply"]["title"]
                elif interactive.get("type") == "list_reply":
                    text = interactive["list_reply"]["title"]
            elif msg.get("type") == "button":
                text = msg["button"]["text"]

            if not text:
                return None

            # phone_number_id identifies which restaurant this is for
            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")

            return IncomingMessage(
                channel="whatsapp",
                sender_id=msg["from"],  # customer's phone number
                restaurant_id=phone_number_id,  # mapped to restaurant later
                text=text,
                metadata={
                    "message_id": msg.get("id", ""),
                    "sender_name": sender_name,
                    "phone_number_id": phone_number_id,
                    "timestamp": msg.get("timestamp", ""),
                },
            )
        except (KeyError, IndexError):
            return None

    def render(self, message: OutgoingMessage) -> dict:
        """Convert canonical OutgoingMessage to WhatsApp API format."""
        # If there are buttons (max 3 for WhatsApp), use interactive message
        if message.buttons and len(message.buttons) <= 3:
            return {
                "messaging_product": "whatsapp",
                "to": message.recipient_id,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": message.text[:1024]},  # WhatsApp limit
                    "action": {
                        "buttons": [
                            {
                                "type": "reply",
                                "reply": {
                                    "id": f"btn_{i}",
                                    "title": btn.label[:20],  # WhatsApp 20 char limit
                                }
                            }
                            for i, btn in enumerate(message.buttons[:3])
                        ]
                    }
                }
            }

        # If more than 3 buttons, use list message
        if message.buttons and len(message.buttons) > 3:
            return {
                "messaging_product": "whatsapp",
                "to": message.recipient_id,
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "body": {"text": message.text[:1024]},
                    "action": {
                        "button": "Choose an option",
                        "sections": [{
                            "title": "Options",
                            "rows": [
                                {
                                    "id": f"row_{i}",
                                    "title": btn.label[:24],
                                    "description": btn.value[:72] if btn.value != btn.label else "",
                                }
                                for i, btn in enumerate(message.buttons[:10])
                            ]
                        }]
                    }
                }
            }

        # Plain text message
        return {
            "messaging_product": "whatsapp",
            "to": message.recipient_id,
            "type": "text",
            "text": {"body": message.text[:4096]},  # WhatsApp limit
        }

    async def send(self, phone_number_id: str, access_token: str, rendered: dict) -> dict | None:
        """Send the rendered message via Meta Graph API."""
        url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=rendered, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"WhatsApp send error: {response.status_code} {response.text}")
                return None
