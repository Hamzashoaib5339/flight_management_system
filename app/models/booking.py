import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Integer,
    Float,
    DateTime,
    Enum as SQLEnum,
    JSON,
    CheckConstraint,
    ForeignKey,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.flight import Flight


class BookingStatus(str, enum.Enum):
    HELD = "HELD"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Booking(Base):
    __tablename__ = "bookings"

    # Primary booking ID
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Passenger booking reference
    pnr: Mapped[str] = mapped_column(
        String(6),
        unique=True,
        index=True,
        nullable=False,
    )

    # Real relationship with Flight
    flight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flights.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    flight: Mapped["Flight"] = relationship(
        "Flight",
        backref="bookings",
    )

    # Passenger information
    passenger_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    passenger_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    passenger_timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="UTC",
    )

    # Booking details
    fare_class: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    seat_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    total_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
    )

    status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus),
        nullable=False,
        default=BookingStatus.HELD,
    )

    # Seat hold information
    hold_token: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # n8n automation tracking
    checkin_reminder_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Idempotency
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
        nullable=True,
        index=True,
    )

    # Database-level validation
    __table_args__ = (
        CheckConstraint(
            "total_price >= 0.0",
            name="check_positive_price",
        ),
        CheckConstraint(
            "seat_count > 0",
            name="check_valid_seat_count",
        ),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    response_body: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )