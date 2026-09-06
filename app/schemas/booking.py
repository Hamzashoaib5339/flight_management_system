import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, EmailStr


class GroupBookingStrategy(str, Enum):
    ALL_OR_NOTHING = "ALL_OR_NOTHING"
    PARTIAL = "PARTIAL"


class FareClassEnum(str, Enum):
    BASIC_ECONOMY = "BASIC_ECONOMY"
    FLEXIBLE = "FLEXIBLE"
    BUSINESS = "BUSINESS"


class CreateHoldRequest(BaseModel):
    # Real Flight UUID
    flight_id: uuid.UUID

    # Passenger information
    passenger_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
    )

    passenger_email: EmailStr

    passenger_timezone: str = Field(
        default="UTC",
        max_length=64,
    )

    # Booking details
    fare_class: FareClassEnum = FareClassEnum.BASIC_ECONOMY

    seat_count: int = Field(
        ...,
        ge=1,
        le=10,
        description="Seats requested (1-10)",
    )

    currency: str = Field(
        default="USD",
        max_length=3,
    )

    group_strategy: GroupBookingStrategy = (
        GroupBookingStrategy.ALL_OR_NOTHING
    )


class HoldResponse(BaseModel):
    pnr: str
    hold_token: str
    flight_id: uuid.UUID
    fare_class: str
    seats_reserved: int
    total_price: float
    currency: str
    expires_at: datetime
    status: str


class ConfirmBookingRequest(BaseModel):
    hold_token: str = Field(
        ...,
        description="Active seat hold token",
    )

    pnr: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-character PNR code",
    )


class ConfirmationResponse(BaseModel):
    pnr: str
    status: str
    flight_id: uuid.UUID
    seats_confirmed: int
    total_price: float
    currency: str
    confirmed_at: datetime