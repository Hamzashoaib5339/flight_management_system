import uuid
import string
from app.models.flight import Seat
from app.schemas.flight import SeatClassConfig

def generate_physical_seats(flight_id: uuid.UUID, seat_classes: list[SeatClassConfig]) -> list[Seat]:
    seats: list[Seat] = []
    row_offset = 1

    for config in seat_classes:
        cols = string.ascii_uppercase[:config.seats_per_row]
        generated_count = 0
        
        for r in range(config.rows):
            current_row = row_offset + r
            for col in cols:
                if generated_count >= config.capacity:
                    break
                seats.append(Seat(
                    flight_id=flight_id,
                    class_type=config.class_type,
                    seat_number=f"{current_row}{col}",
                    is_booked=False
                ))
                generated_count += 1
            if generated_count >= config.capacity:
                break
        
        row_offset += config.rows

    return seats