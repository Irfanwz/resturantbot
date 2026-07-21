import uuid
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None  # auto-generated if not provided


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    suggestions: list[str] = Field(default_factory=list)  # quick reply buttons
    cart_summary: dict | None = None  # current cart state if relevant


class Button(BaseModel):
    label: str
    value: str


class Media(BaseModel):
    type: str  # "image", "document"
    url: str
    caption: str | None = None
