from typing import Optional
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.booking import (
    CreateHoldRequest, 
    HoldResponse, 
    ConfirmBookingRequest, 
    ConfirmationResponse
)
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["Seat Holds & Booking Engine"])

@router.post("/hold", response_model=HoldResponse, status_code=status.HTTP_201_CREATED)
async def create_seat_hold(
    payload: CreateHoldRequest,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Reserve seats with atomic row locks, cutoff rules, and overbooking multipliers.
    Supports X-Idempotency-Key header to prevent double booking on client retry.
    """
    return await BookingService.create_seat_hold(
        db=db, 
        payload=payload, 
        idempotency_key=x_idempotency_key
    )

@router.post("/confirm", response_model=ConfirmationResponse, status_code=status.HTTP_200_OK)
async def confirm_booking(
    payload: ConfirmBookingRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Confirm an active seat hold and issue final PNR confirmation."""
    return await BookingService.confirm_booking(db=db, payload=payload)