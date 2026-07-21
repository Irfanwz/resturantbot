import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from restaurant_bot.config import settings

ALGORITHM = "HS256"


def create_access_token(user_id: uuid.UUID, restaurant_id: uuid.UUID | None = None, role: str = "owner") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "restaurant_id": str(restaurant_id) if restaurant_id else None,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
