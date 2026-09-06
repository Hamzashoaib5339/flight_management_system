from datetime import datetime, timezone
from typing import Annotated, Optional
from pydantic import BaseModel, Field, model_validator, StringConstraints

from app.models.flight import SeatClassType, FlightStatus

IATAString = Annotated[str, StringConstraints(to_upper=True, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]
FlightNumString = Annotated[str, StringConstraints(to_upper=True, min_length=2, max_length=10, pattern=r"^[A-Z0-9]+$")]

class SeatClassConfig(BaseModel):
    class_type: SeatClassType
    capacity: int = Field(gt=0, description="Capacity must be a positive integer")
    rows: int = Field(gt=0, description="Number of rows for seat mapping")
    seats_per_row: int = Field(gt=0, description="Seats per row")

class FlightCreateRequest(BaseModel):
    flight_number: FlightNumString
    origin: IATAString
    destination: IATAString
    departure_time: datetime
    arrival_time: datetime
    total_capacity: int = Field(gt=0)
    seat_classes: list[SeatClassConfig]

    @model_validator(mode="after")
    def validate_flight_payload(self) -> "FlightCreateRequest":
        if self.origin == self.destination:
            raise ValueError("Origin and destination cannot be identical")
        
        if self.departure_time <= datetime.now(timezone.utc):
            raise ValueError("Departure time must be in the future")
            
        if self.arrival_time <= self.departure_time:
            raise ValueError("Arrival time must be strictly after departure time")

        total_class_seats = sum(c.capacity for c in self.seat_classes)
        if total_class_seats != self.total_capacity:
            raise ValueError(
                f"Sum of class capacities ({total_class_seats}) must equal total capacity ({self.total_capacity})"
            )

        for c in self.seat_classes:
            if c.rows * c.seats_per_row < c.capacity:
                raise ValueError(
                    f"Layout grid for {c.class_type} ({c.rows}x{c.seats_per_row}) "
                    f"cannot accommodate capacity of {c.capacity}"
                )
        return self

class FlightUpdateRequest(BaseModel):
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    status: Optional[FlightStatus] = None
    class_capacity_updates: Optional[dict[SeatClassType, int]] = None

    @model_validator(mode="after")
    def validate_updates(self) -> "FlightUpdateRequest":
        if self.departure_time and self.arrival_time and self.arrival_time <= self.departure_time:
            raise ValueError("Arrival time must be strictly after departure time")
        
        if self.class_capacity_updates:
            for class_type, cap in self.class_capacity_updates.items():
                if cap <= 0:
                    raise ValueError(f"Capacity for {class_type} must be a positive integer")
        return self