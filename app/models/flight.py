import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Index, CheckConstraint, 
    UniqueConstraint, Enum as SQLEnum, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class FlightStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"

class SeatClassType(str, Enum):
    FIRST = "FIRST"
    BUSINESS = "BUSINESS"
    ECONOMY = "ECONOMY"

class Flight(Base):
    __tablename__ = "flights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_number: Mapped[str] = mapped_column(String(10), nullable=False)
    origin: Mapped[str] = mapped_column(String(3), nullable=False)
    destination: Mapped[str] = mapped_column(String(3), nullable=False)
    departure_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[FlightStatus] = mapped_column(SQLEnum(FlightStatus), default=FlightStatus.SCHEDULED, nullable=False)

    seat_classes: Mapped[list["FlightSeatClass"]] = relationship("FlightSeatClass", back_populates="flight", cascade="all, delete-orphan")
    seats: Mapped[list["Seat"]] = relationship("Seat", back_populates="flight", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total_capacity > 0", name="chk_positive_flight_capacity"),
        CheckConstraint("arrival_time > departure_time", name="chk_valid_flight_times"),
        Index(
            "uq_flight_num_route_date",
            flight_number, origin, destination,
               text("((departure_time AT TIME ZONE 'UTC')::date)"),
            unique=True
        ),
    )

class FlightSeatClass(Base):
    __tablename__ = "flight_seat_classes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), nullable=False)
    class_type: Mapped[SeatClassType] = mapped_column(SQLEnum(SeatClassType), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    flight: Mapped["Flight"] = relationship("Flight", back_populates="seat_classes")

    __table_args__ = (
        CheckConstraint("capacity > 0", name="chk_positive_class_capacity"),
        UniqueConstraint("flight_id", "class_type", name="uq_flight_class_type"),
    )

class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"), nullable=False)
    class_type: Mapped[SeatClassType] = mapped_column(SQLEnum(SeatClassType), nullable=False)
    seat_number: Mapped[str] = mapped_column(String(5), nullable=False)
    is_booked: Mapped[bool] = mapped_column(default=False, nullable=False)

    flight: Mapped["Flight"] = relationship("Flight", back_populates="seats")

    __table_args__ = (
        UniqueConstraint("flight_id", "seat_number", name="uq_flight_seat_number"),
        Index("idx_flight_seat_class_booked", "flight_id", "class_type", "is_booked"),
    )