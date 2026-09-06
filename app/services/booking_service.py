import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus, IdempotencyRecord
from app.models.flight import (
    Flight,
    FlightSeatClass,
    FlightStatus,
    SeatClassType,
)
from app.schemas.booking import (
    CreateHoldRequest,
    ConfirmBookingRequest,
    GroupBookingStrategy,
)


# ============================================================
# BOOKING POLICY CONFIGURATION
# ============================================================

# Maximum percentage of physical capacity that can be booked.
OVERBOOKING_LIMITS = {
    "BASIC_ECONOMY": 1.00,
    "FLEXIBLE": 1.05,
    "BUSINESS": 1.02,
}

# Booking cutoff before flight departure.
CUTOFF_MINUTES = {
    "BASIC_ECONOMY": 120,
    "FLEXIBLE": 60,
    "BUSINESS": 30,
}

# How long a seat hold remains active.
HOLD_DURATION_MINUTES = {
    "BASIC_ECONOMY": 5,
    "FLEXIBLE": 15,
    "BUSINESS": 30,
}

# Temporary pricing configuration.
# This can later be moved into the database.
BASE_PRICE = {
    "BASIC_ECONOMY": 350.0,
    "FLEXIBLE": 520.0,
    "BUSINESS": 1800.0,
}

# Maps booking fare products to actual physical flight seat classes.
FARE_CLASS_TO_SEAT_CLASS = {
    "BASIC_ECONOMY": SeatClassType.ECONOMY,
    "FLEXIBLE": SeatClassType.ECONOMY,
    "BUSINESS": SeatClassType.BUSINESS,
}


class BookingService:

    @staticmethod
    def generate_pnr() -> str:
        """Generate a random 6-character uppercase alphanumeric PNR."""
        characters = string.ascii_uppercase + string.digits
        return "".join(
            secrets.choice(characters)
            for _ in range(6)
        )

    # ========================================================
    # IDEMPOTENCY
    # ========================================================

    @classmethod
    async def check_idempotency(
        cls,
        db: AsyncSession,
        key: Optional[str],
    ) -> Optional[Dict[str, Any]]:

        if not key:
            return None

        result = await db.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.idempotency_key == key
            )
        )

        record = result.scalars().first()

        if record:

            if record.status == "PROCESSING":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "A request with this Idempotency-Key "
                        "is currently being processed."
                    ),
                )

            if record.status == "COMPLETED":
                return record.response_body

        # Create an idempotency lock.
        new_record = IdempotencyRecord(
            idempotency_key=key,
            status="PROCESSING",
        )

        db.add(new_record)

        try:
            await db.commit()
        except Exception:
            await db.rollback()

            # Another concurrent request may have inserted the key.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Unable to acquire idempotency lock. "
                    "Please retry the request."
                ),
            )

        return None

    @classmethod
    async def save_idempotency_response(
        cls,
        db: AsyncSession,
        key: Optional[str],
        response_body: Dict[str, Any],
    ) -> None:

        if not key:
            return

        result = await db.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.idempotency_key == key
            )
        )

        record = result.scalars().first()

        if record:
            record.status = "COMPLETED"
            record.response_body = response_body

            await db.commit()

    # ========================================================
    # CREATE SEAT HOLD
    # ========================================================

    @classmethod
    async def create_seat_hold(
        cls,
        db: AsyncSession,
        payload: CreateHoldRequest,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:

        # ----------------------------------------------------
        # 1. IDEMPOTENCY CHECK
        # ----------------------------------------------------

        cached_response = await cls.check_idempotency(
            db=db,
            key=idempotency_key,
        )

        if cached_response:
            return cached_response

        now = datetime.now(timezone.utc)
        fare_class = payload.fare_class.value

        # ----------------------------------------------------
        # 2. FIND AND LOCK THE REAL FLIGHT
        # ----------------------------------------------------

        flight_result = await db.execute(
            select(Flight)
            .where(Flight.id == payload.flight_id)
            .with_for_update()
        )

        flight = flight_result.scalar_one_or_none()

        if not flight:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flight not found.",
            )

        # ----------------------------------------------------
        # 3. VALIDATE FLIGHT STATUS
        # ----------------------------------------------------

        if flight.status == FlightStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book a cancelled flight.",
            )

        if flight.status == FlightStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book a completed flight.",
            )

        # ----------------------------------------------------
        # 4. VALIDATE DEPARTURE TIME
        # ----------------------------------------------------

        if flight.departure_time.tzinfo is None:
            departure_time = flight.departure_time.replace(
                tzinfo=timezone.utc
            )
        else:
            departure_time = flight.departure_time

        if departure_time <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This flight has already departed.",
            )

        # ----------------------------------------------------
        # 5. BOOKING CUTOFF RULE
        # ----------------------------------------------------

        cutoff_minutes = CUTOFF_MINUTES.get(
            fare_class,
            120,
        )

        cutoff_margin = timedelta(
            minutes=cutoff_minutes
        )

        if departure_time - now < cutoff_margin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Booking window closed for {fare_class}. "
                    f"Cutoff is {cutoff_minutes} minutes "
                    "before departure."
                ),
            )

        # ----------------------------------------------------
        # 6. MAP FARE CLASS TO PHYSICAL SEAT CLASS
        # ----------------------------------------------------

        seat_class_type = FARE_CLASS_TO_SEAT_CLASS.get(
            fare_class
        )

        if not seat_class_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid fare class: {fare_class}",
            )

        # ----------------------------------------------------
        # 7. FIND AND LOCK SEAT CLASS
        # ----------------------------------------------------

        seat_class_result = await db.execute(
            select(FlightSeatClass)
            .where(
                FlightSeatClass.flight_id == flight.id,
                FlightSeatClass.class_type == seat_class_type,
            )
            .with_for_update()
        )

        flight_seat_class = (
            seat_class_result.scalar_one_or_none()
        )

        if not flight_seat_class:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"{fare_class} is not available "
                    "for this flight."
                ),
            )

        # ----------------------------------------------------
        # 8. CALCULATE OCCUPIED SEATS
        # ----------------------------------------------------

        occupied_query = (
            select(
                func.coalesce(
                    func.sum(Booking.seat_count),
                    0,
                )
            )
            .where(
                Booking.flight_id == flight.id,
                Booking.fare_class == fare_class,
                Booking.status.in_(
                    [
                        BookingStatus.HELD,
                        BookingStatus.CONFIRMED,
                    ]
                ),
            )
        )

        occupied_result = await db.execute(
            occupied_query
        )

        currently_occupied = (
            occupied_result.scalar_one()
        )

        # ----------------------------------------------------
        # 9. APPLY OVERBOOKING POLICY
        # ----------------------------------------------------

        overbooking_factor = OVERBOOKING_LIMITS.get(
            fare_class,
            1.0,
        )

        max_allowed_seats = int(
            flight_seat_class.capacity
            * overbooking_factor
        )

        available_seats = (
            max_allowed_seats
            - currently_occupied
        )

        # ----------------------------------------------------
        # 10. GROUP BOOKING STRATEGY
        # ----------------------------------------------------

        seats_to_reserve = payload.seat_count

        if available_seats < payload.seat_count:

            if (
                payload.group_strategy
                == GroupBookingStrategy.ALL_OR_NOTHING
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Requested {payload.seat_count} seats, "
                        f"but only "
                        f"{max(0, available_seats)} "
                        "are available."
                    ),
                )

            seats_to_reserve = available_seats

            if seats_to_reserve <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "No seats are available in this class."
                    ),
                )

        # ----------------------------------------------------
        # 11. GENERATE BOOKING HOLD
        # ----------------------------------------------------

        pnr = cls.generate_pnr()

        hold_token = (
            "HOLD-"
            + secrets.token_hex(16).upper()
        )

        hold_minutes = HOLD_DURATION_MINUTES.get(
            fare_class,
            15,
        )

        expires_at = now + timedelta(
            minutes=hold_minutes
        )

        # ----------------------------------------------------
        # 12. CALCULATE PRICE
        # ----------------------------------------------------

        unit_price = BASE_PRICE.get(
            fare_class,
            300.0,
        )

        total_price = round(
            unit_price * seats_to_reserve,
            2,
        )

        # ----------------------------------------------------
        # 13. CREATE BOOKING
        # ----------------------------------------------------

        new_booking = Booking(
            pnr=pnr,
            flight_id=flight.id,

            passenger_name=payload.passenger_name,
            passenger_email=str(
                payload.passenger_email
            ),
            passenger_timezone=payload.passenger_timezone,

            fare_class=fare_class,
            seat_count=seats_to_reserve,

            total_price=total_price,
            currency=payload.currency.upper(),

            status=BookingStatus.HELD,

            hold_token=hold_token,
            expires_at=expires_at,

            checkin_reminder_sent=False,

            idempotency_key=idempotency_key,
        )

        db.add(new_booking)

        try:
            await db.commit()
            await db.refresh(new_booking)

        except Exception:
            await db.rollback()
            raise

        # ----------------------------------------------------
        # 14. PREPARE RESPONSE
        # ----------------------------------------------------

        response = {
            "pnr": new_booking.pnr,
            "hold_token": new_booking.hold_token,
            "flight_id": str(new_booking.flight_id),
            "fare_class": new_booking.fare_class,
            "seats_reserved": new_booking.seat_count,
            "total_price": new_booking.total_price,
            "currency": new_booking.currency,
            "expires_at": new_booking.expires_at,
            "status": new_booking.status.value,
        }

        # ----------------------------------------------------
        # 15. SAVE IDEMPOTENCY RESPONSE
        # ----------------------------------------------------

        await cls.save_idempotency_response(
            db=db,
            key=idempotency_key,
            response_body=response,
        )

        return response

    # ========================================================
    # CONFIRM BOOKING
    # ========================================================

    @classmethod
    async def confirm_booking(
        cls,
        db: AsyncSession,
        payload: ConfirmBookingRequest,
    ) -> Dict[str, Any]:

        now = datetime.now(timezone.utc)

        # ----------------------------------------------------
        # 1. FIND AND LOCK BOOKING
        # ----------------------------------------------------

        result = await db.execute(
            select(Booking)
            .where(
                Booking.pnr == payload.pnr,
                Booking.hold_token == payload.hold_token,
            )
            .with_for_update()
        )

        booking = result.scalars().first()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Booking hold not found or "
                    "invalid PNR/Token pair."
                ),
            )

        # ----------------------------------------------------
        # 2. ALREADY CONFIRMED
        # ----------------------------------------------------

        if booking.status == BookingStatus.CONFIRMED:

            return {
                "pnr": booking.pnr,
                "status": booking.status.value,
                "flight_id": str(booking.flight_id),
                "seats_confirmed": booking.seat_count,
                "total_price": booking.total_price,
                "currency": booking.currency,
                "confirmed_at": booking.created_at,
            }

        # ----------------------------------------------------
        # 3. HOLD EXPIRED
        # ----------------------------------------------------

        if (
            booking.status != BookingStatus.HELD
            or (
                booking.expires_at is not None
                and booking.expires_at < now
            )
        ):

            booking.status = BookingStatus.EXPIRED

            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail=(
                    "Seat hold has expired. "
                    "Please create a new seat hold."
                ),
            )

        # ----------------------------------------------------
        # 4. CONFIRM BOOKING
        # ----------------------------------------------------

        booking.status = BookingStatus.CONFIRMED

        await db.commit()
        await db.refresh(booking)

        # ----------------------------------------------------
        # 5. RETURN CONFIRMATION
        # ----------------------------------------------------

        return {
            "pnr": booking.pnr,
            "status": booking.status.value,
            "flight_id": str(booking.flight_id),
            "seats_confirmed": booking.seat_count,
            "total_price": booking.total_price,
            "currency": booking.currency,
            "confirmed_at": now,
        }