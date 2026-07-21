import uuid
from datetime import date, time, datetime, timezone
from sqlalchemy import String, Boolean, Integer, Text, ForeignKey, Uuid, Date, Time, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from restaurant_bot.db.base import Base, TimestampMixin, TenantMixin

class Table(Base, TenantMixin):
    __tablename__ = "tables"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    table_number: Mapped[str] = mapped_column(String(20))
    capacity: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="table")

class Reservation(Base, TimestampMixin, TenantMixin):
    __tablename__ = "reservations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"))
    table_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tables.id"), nullable=True)
    party_size: Mapped[int] = mapped_column(Integer)
    reservation_date: Mapped[date] = mapped_column(Date)
    reservation_time: Mapped[time] = mapped_column(Time)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=90)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, confirmed, seated, completed, cancelled, no_show
    special_requests: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str] = mapped_column(String(50))

    table: Mapped["Table | None"] = relationship(back_populates="reservations")
