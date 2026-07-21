import uuid
from datetime import date, time
from pydantic import BaseModel, Field


class ReservationCreate(BaseModel):
    party_size: int = Field(..., ge=1)
    reservation_date: date
    reservation_time: time
    special_requests: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None


class ReservationResponse(BaseModel):
    id: uuid.UUID
    party_size: int
    reservation_date: date
    reservation_time: time
    duration_minutes: int
    status: str
    special_requests: str | None
    table_number: str | None = None

    model_config = {"from_attributes": True}


class ReservationStatusUpdate(BaseModel):
    status: str  # confirmed, seated, completed, cancelled, no_show


class TableResponse(BaseModel):
    id: uuid.UUID
    table_number: str
    capacity: int
    is_active: bool

    model_config = {"from_attributes": True}


class AvailabilityRequest(BaseModel):
    date: date
    time: time
    party_size: int = Field(..., ge=1)


class AvailabilityResponse(BaseModel):
    available: bool
    available_slots: list[str] = Field(default_factory=list)  # ["18:00", "18:30", "19:00"]
    message: str
