import uuid
from datetime import datetime, time, timezone
from sqlalchemy import String, Boolean, Integer, Text, JSON, ForeignKey, Uuid, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from restaurant_bot.db.base import Base, TimestampMixin

class Restaurant(Base, TimestampMixin):
    __tablename__ = "restaurants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free, pro, enterprise
    config: Mapped[dict] = mapped_column(JSON, default=dict)  # RestaurantConfig JSON

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="restaurant")
    operating_hours: Mapped[list["OperatingHours"]] = relationship(back_populates="restaurant")

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default="owner")  # owner, manager, staff, superadmin
    restaurant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("restaurants.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    restaurant: Mapped["Restaurant | None"] = relationship(back_populates="users")

class OperatingHours(Base):
    __tablename__ = "operating_hours"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("restaurants.id"), index=True)
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0=Monday, 6=Sunday
    open_time: Mapped[time] = mapped_column(Time)
    close_time: Mapped[time] = mapped_column(Time)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)

    restaurant: Mapped["Restaurant"] = relationship(back_populates="operating_hours")
