import uuid
from fastapi import Request, HTTPException


async def resolve_restaurant_id(request: Request) -> uuid.UUID | None:
    """Extract restaurant_id from the URL path if present."""
    restaurant_id = request.path_params.get("restaurant_id")
    if restaurant_id:
        try:
            return uuid.UUID(str(restaurant_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid restaurant ID")
    return None
