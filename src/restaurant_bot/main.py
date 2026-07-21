from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text
from restaurant_bot.config import settings
from restaurant_bot.api.v1.router import api_v1_router
from restaurant_bot.db.engine import engine
from restaurant_bot.db.base import Base

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if using SQLite (dev mode)
    if "sqlite" in settings.database_url:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="Restaurant Bot API",
    description="AI-powered restaurant bot — plug and play, channel-agnostic, multi-tenant",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_v1_router)

# Serve static files (chat UI, widget)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/ready")
async def ready():
    """Readiness probe - checks if the app can handle requests."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "not ready"})


@app.get("/")
async def root():
    return {
        "name": "Restaurant Bot API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
