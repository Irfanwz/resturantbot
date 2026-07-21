import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from restaurant_bot.auth.jwt import decode_access_token

security = HTTPBearer()


class CurrentUser:
    def __init__(self, user_id: uuid.UUID, restaurant_id: uuid.UUID | None, role: str):
        self.user_id = user_id
        self.restaurant_id = restaurant_id
        self.role = role


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return CurrentUser(
        user_id=uuid.UUID(payload["sub"]),
        restaurant_id=uuid.UUID(payload["restaurant_id"]) if payload.get("restaurant_id") else None,
        role=payload.get("role", "owner"),
    )


async def require_owner(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in ("owner", "superadmin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required")
    return user


async def require_staff(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in ("owner", "manager", "staff", "superadmin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")
    return user


async def require_superadmin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return user
