import html
import re
import httpx
from restaurant_bot.channels.base import ChannelAdapter, IncomingMessage, OutgoingMessage


class TelegramAdapter(ChannelAdapter):
    """
    Telegram Bot API adapter.
    Normalizes Telegram updates to canonical messages,
    renders responses with inline keyboards,
    and sends via Telegram Bot API.
    """

    def normalize(self, raw_payload: dict) -> IncomingMessage | None:
        """Parse Telegram update payload into a canonical IncomingMessage."""
        try:
            # Regular text message
            if raw_payload.get("message"):
                msg = raw_payload["message"]
                text = msg.get("text", "")
                if not text:
                    return None
                chat_id = str(msg["chat"]["id"])
                sender_name = msg.get("from", {}).get("first_name", "")
                return IncomingMessage(
                    channel="telegram",
                    sender_id=chat_id,
                    restaurant_id="",  # resolved by restaurant_id in webhook URL
                    text=text,
                    metadata={
                        "sender_name": sender_name,
                        "update_id": str(raw_payload.get("update_id", "")),
                        "callback_query_id": "",
                    },
                )

            # Inline keyboard button press
            if raw_payload.get("callback_query"):
                cq = raw_payload["callback_query"]
                text = cq.get("data", "")
                if not text:
                    return None
                chat_id = str(cq["message"]["chat"]["id"])
                sender_name = cq.get("from", {}).get("first_name", "")
                return IncomingMessage(
                    channel="telegram",
                    sender_id=chat_id,
                    restaurant_id="",
                    text=text,
                    metadata={
                        "sender_name": sender_name,
                        "update_id": str(raw_payload.get("update_id", "")),
                        "callback_query_id": cq.get("id", ""),
                    },
                )

        except (KeyError, IndexError, TypeError):
            pass
        return None

    def render(self, message: OutgoingMessage) -> dict:
        """Convert canonical OutgoingMessage to Telegram sendMessage payload."""
        # Escape HTML special chars, then convert **bold** markdown to <b>
        text = html.escape(message.text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = text[:4096]  # Telegram message limit

        if message.buttons:
            # Each button on its own row (inline keyboard)
            keyboard = {
                "inline_keyboard": [
                    [{"text": btn.label, "callback_data": (btn.value or btn.label)[:64]}]
                    for btn in message.buttons[:10]
                ]
            }
            return {
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": keyboard,
            }

        return {
            "text": text,
            "parse_mode": "HTML",
        }

    async def send(self, bot_token: str, chat_id: str, rendered: dict) -> dict | None:
        """Send a message via Telegram Bot API."""
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, **rendered}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                return response.json()
            print(f"Telegram send error: {response.status_code} {response.text}")
            return None

    async def answer_callback(self, bot_token: str, callback_query_id: str) -> None:
        """Acknowledge a callback query to dismiss Telegram's loading indicator."""
        url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
        async with httpx.AsyncClient() as client:
            await client.post(url, json={"callback_query_id": callback_query_id})

    async def set_webhook(self, bot_token: str, webhook_url: str) -> dict:
        """Register this server's URL as the Telegram webhook."""
        url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={"url": webhook_url, "allowed_updates": ["message", "callback_query"]})
            return response.json()

    async def get_me(self, bot_token: str) -> dict | None:
        """Fetch bot info (id, username, first_name)."""
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.json().get("result")
            return None
