import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from app.core.database import get_db_session
from app.core.security import AuthUser, Role, require_roles
from app.models.flight import Flight, FlightSeatClass, Seat, FlightStatus
from app.schemas.flight import FlightCreateRequest, FlightUpdateRequest
from app.services.seat_service import generate_physical_seats
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/admin/flights", tags=["Admin Flight Management"])

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_flight(
    payload: FlightCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: AuthUser = Depends(require_roles([Role.SUPER_ADMIN, Role.OPS_AGENT]))
):
    async with db.begin():
        flight = Flight(
            flight_number=payload.flight_number,
            origin=payload.origin,
            destination=payload.destination,
            departure_time=payload.departure_time,
            arrival_time=payload.arrival_time,
            total_capacity=payload.total_capacity,
            status=FlightStatus.SCHEDULED
        )
        db.add(flight)
        await db.flush()

        for sc in payload.seat_classes:
            db.add(FlightSeatClass(
                flight_id=flight.id,
                class_type=sc.class_type,
                capacity=sc.capacity
            ))

        seats = generate_physical_seats(flight.id, payload.seat_classes)
        db.add_all(seats)

        await write_audit_log(
            db, user, "FLIGHT_CREATE", "Flight", flight.id, payload.model_dump(mode="json")
        )

        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            if "uq_flight_num_route_date" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Flight {payload.flight_number} already exists on route {payload.origin}->{payload.destination} for this date."
                )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Database integrity violation")

    return {"flight_id": flight.id, "status": "CREATED"}

@router.patch("/{flight_id}")
async def update_flight(
    flight_id: uuid.UUID,
    payload: FlightUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: AuthUser = Depends(require_roles([Role.SUPER_ADMIN, Role.OPS_AGENT]))
):
    async with db.begin():
        result = await db.execute(
            select(Flight).where(Flight.id == flight_id).with_for_update()
        )
        flight = result.scalar_one_or_none()
        if not flight:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight not found")

        if flight.status == FlightStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a cancelled flight"
            )

        changes: dict[str, Any] = {}

        if payload.class_capacity_updates:
            for class_type, new_cap in payload.class_capacity_updates.items():
                booked_query = await db.execute(
                    select(func.count(Seat.id))
                    .where(
                        Seat.flight_id == flight_id,
                        Seat.class_type == class_type,
                        Seat.is_booked == True
                    )
                )
                booked_count = booked_query.scalar_one()

                if new_cap < booked_count:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot reduce capacity for {class_type} to {new_cap}. Currently booked seats: {booked_count}"
                    )

                sc_res = await db.execute(
                    select(FlightSeatClass).where(
                        FlightSeatClass.flight_id == flight_id,
                        FlightSeatClass.class_type == class_type
                    )
                )
                sc_obj = sc_res.scalar_one_or_none()
                if sc_obj:
                    changes[f"capacity_{class_type}"] = {"old": sc_obj.capacity, "new": new_cap}
                    sc_obj.capacity = new_cap

        if payload.departure_time:
            changes["departure_time"] = {"old": flight.departure_time.isoformat(), "new": payload.departure_time.isoformat()}
            flight.departure_time = payload.departure_time
            
        if payload.arrival_time:
            changes["arrival_time"] = {"old": flight.arrival_time.isoformat(), "new": payload.arrival_time.isoformat()}
            flight.arrival_time = payload.arrival_time

        if payload.status and payload.status != flight.status:
            changes["status"] = {"old": flight.status.value, "new": payload.status.value}
            flight.status = payload.status

            if payload.status == FlightStatus.CANCELLED:
                changes["n8n_notification_triggered"] = True

        await write_audit_log(db, user, "FLIGHT_UPDATE", "Flight", flight.id, changes)
        await db.commit()

    return {"flight_id": flight_id, "updated_fields": list(changes.keys())}