import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_bot.db.engine import get_db
from restaurant_bot.db.models.restaurant import Restaurant, User
from restaurant_bot.auth.password import hash_password, verify_password
from restaurant_bot.auth.jwt import create_access_token
from restaurant_bot.schemas.config import RestaurantConfig

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""
    restaurant_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    restaurant_id: str | None = None
    role: str


def slugify(name: str) -> str:
    import re
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create restaurant with default config
    slug = slugify(req.restaurant_name)
    # Ensure unique slug
    slug_check = await db.execute(select(Restaurant).where(Restaurant.slug == slug))
    if slug_check.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    default_config = RestaurantConfig()
    restaurant = Restaurant(
        name=req.restaurant_name,
        slug=slug,
        config=default_config.model_dump(mode="json"),
    )
    db.add(restaurant)
    await db.flush()

    # Create user
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role="owner",
        restaurant_id=restaurant.id,
    )
    db.add(user)
    await db.flush()

    token = create_access_token(user.id, restaurant.id, user.role)
    return AuthResponse(
        access_token=token,
        user_id=str(user.id),
        restaurant_id=str(restaurant.id),
        role=user.role,
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token(user.id, user.restaurant_id, user.role)
    return AuthResponse(
        access_token=token,
        user_id=str(user.id),
        restaurant_id=str(user.restaurant_id) if user.restaurant_id else None,
        role=user.role,
    )
