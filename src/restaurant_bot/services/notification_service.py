import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from decimal import Decimal

import httpx
from restaurant_bot.schemas.config import RestaurantConfig

logger = logging.getLogger(__name__)


async def send_order_email(
    to_email: str,
    restaurant_name: str,
    order_number: str,
    order_total: str,
    order_type: str,
    items_summary: str,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_password: str = "",
):
    """Send order notification email to restaurant owner."""
    if not smtp_user or not smtp_password or not to_email:
        return False

    subject = f"New Order #{order_number} — {restaurant_name}"

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 500px;">
        <div style="background: #FF6B35; color: white; padding: 16px 24px; border-radius: 8px 8px 0 0;">
            <h2 style="margin:0;">New Order!</h2>
        </div>
        <div style="border: 1px solid #e5e7eb; padding: 24px; border-radius: 0 0 8px 8px;">
            <p><strong>Order #:</strong> {order_number}</p>
            <p><strong>Type:</strong> {order_type}</p>
            <p><strong>Total:</strong> {order_total}</p>
            <hr style="border:none; border-top:1px solid #e5e7eb;">
            <p><strong>Items:</strong></p>
            <p>{items_summary}</p>
            <hr style="border:none; border-top:1px solid #e5e7eb;">
            <p style="color:#666; font-size:12px;">This notification was sent by {restaurant_name}'s Restaurant Bot.</p>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email notification failed: {e}")
        return False


def build_wa_notification_link(
    owner_phone: str,
    restaurant_name: str,
    order_number: str,
    order_total: str,
    order_type: str,
    items_summary: str,
) -> str | None:
    """Build a wa.me link to notify the restaurant owner about a new order."""
    if not owner_phone:
        return None

    phone = owner_phone.replace("+", "").replace(" ", "").replace("-", "")

    message = (
        f"\U0001f514 *New Order \u2014 {restaurant_name}*\n\n"
        f"\U0001f4cb Order #: {order_number}\n"
        f"\U0001f37d\ufe0f Type: {order_type}\n"
        f"\U0001f4b0 Total: {order_total}\n\n"
        f"\U0001f4e6 Items:\n{items_summary}\n\n"
        f"Open your admin panel to manage this order."
    )

    return f"https://wa.me/{phone}?text={__import__('urllib.parse', fromlist=['quote']).quote(message)}"


async def send_telegram_order_notification(
    bot_token: str,
    chat_id: str,
    restaurant_name: str,
    order_number: str,
    order_total: str,
    order_type: str,
    items_summary: str,
) -> bool:
    """Send new order notification to restaurant owner's Telegram."""
    logger.info(f"[TG NOTIFY] Attempting to send order notification. bot_token={'SET' if bot_token else 'EMPTY'}, chat_id={chat_id}, order={order_number}")

    if not bot_token or not chat_id:
        logger.warning(f"[TG NOTIFY] SKIPPED — bot_token={'SET' if bot_token else 'EMPTY'}, chat_id={chat_id or 'EMPTY'}")
        return False

    text = (
        f"🔔 <b>New Order — {restaurant_name}</b>\n\n"
        f"📋 Order #: <b>{order_number}</b>\n"
        f"🍽️ Type: {order_type}\n"
        f"💰 Total: <b>{order_total}</b>\n\n"
        f"📦 Items:\n{items_summary}\n\n"
        f"<i>Open admin panel to manage this order.</i>"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            })
            logger.info(f"[TG NOTIFY] Response: status={resp.status_code}, body={resp.text[:200]}")
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"[TG NOTIFY] FAILED: {e}")
        return False
