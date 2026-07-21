from fastapi import APIRouter

from restaurant_bot.api.v1 import auth, chat, menu, config, orders, reservations, analytics, tables, auto_replies, faqs, webhooks

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth.router)
api_v1_router.include_router(chat.router)
api_v1_router.include_router(menu.router)
api_v1_router.include_router(config.router)
api_v1_router.include_router(orders.router)
api_v1_router.include_router(reservations.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(tables.router)
api_v1_router.include_router(auto_replies.router)
api_v1_router.include_router(faqs.router)
api_v1_router.include_router(webhooks.router)
