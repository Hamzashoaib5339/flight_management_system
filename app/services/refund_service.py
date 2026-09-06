import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.booking import Booking, BookingStatus
from app.models.refund import RefundRecord, RefundType, RefundStatus, TravelCredit
from app.schemas.refund import CancellationRequest, ScheduleChangeRequest

# Policy rules by fare class
CANCELLATION_POLICIES = {
    "BASIC_ECONOMY": {
        "type": RefundType.NON_REFUNDABLE,
        "fee_pct": 100.0,
        "allow_credit": False
    },
    "FLEXIBLE": {
        "type": RefundType.CASH_REFUND,
        "fee_pct": 0.0,
        "allow_credit": False
    },
    "BUSINESS": {
        "type": RefundType.CASH_REFUND,
        "fee_pct": 0.0,
        "allow_credit": False
    }
}

class RefundService:

    @staticmethod
    def generate_credit_code() -> str:
        return f"TC-{secrets.token_hex(6).upper()}"

    @classmethod
    async def process_cancellation(
        cls, db: AsyncSession, payload: CancellationRequest
    ) -> Dict[str, Any]:
        """Handles voluntary passenger cancellations with partial seat support and policy branching."""
        now = datetime.now(timezone.utc)

        # 1. Row Lock booking record
        stmt = select(Booking).where(Booking.pnr == payload.pnr).with_for_update()
        result = await db.execute(stmt)
        booking = result.scalars().first()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking with PNR {payload.pnr} not found."
            )

        if booking.status not in [BookingStatus.CONFIRMED, BookingStatus.HELD]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Booking status is {booking.status.value}. Only active bookings can be cancelled."
            )

        if payload.seats_to_cancel > booking.seat_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel {payload.seats_to_cancel} seats. PNR only has {booking.seat_count} seats."
            )

        # 2. Evaluate Policy
        policy = CANCELLATION_POLICIES.get(booking.fare_class, CANCELLATION_POLICIES["BASIC_ECONOMY"])
        per_seat_price = booking.total_price / booking.seat_count
        cancel_gross_price = round(per_seat_price * payload.seats_to_cancel, 2)
        
        cancellation_fee = round((policy["fee_pct"] / 100.0) * cancel_gross_price, 2)
        net_refund = round(cancel_gross_price - cancellation_fee, 2)

        credit_code = None
        credit_expires_at = None

        # 3. Handle Travel Credit vs Cash
        refund_type = policy["type"]
        refund_status = RefundStatus.APPROVED if net_refund > 0 else RefundStatus.PROCESSED

        if refund_type == RefundType.TRAVEL_CREDIT and net_refund > 0:
            credit_code = cls.generate_credit_code()
            credit_expires_at = now + timedelta(days=365) # 1 year credit validity
            
            travel_credit = TravelCredit(
                credit_code=credit_code,
                pnr=booking.pnr,
                amount=net_refund,
                currency=booking.currency,
                expires_at=credit_expires_at
            )
            db.add(travel_credit)
            refund_status = RefundStatus.PROCESSED

        # 4. Create Refund Record
        refund_record = RefundRecord(
            pnr=booking.pnr,
            seats_cancelled=payload.seats_to_cancel,
            original_total=cancel_gross_price,
            cancellation_fee=cancellation_fee,
            net_refund_amount=net_refund,
            currency=booking.currency,
            refund_type=refund_type,
            status=refund_status,
            reason=payload.reason,
            processed_at=now if refund_status == RefundStatus.PROCESSED else None
        )
        db.add(refund_record)

        # 5. Update or Cancel Booking Seats
        remaining_seats = booking.seat_count - payload.seats_to_cancel
        if remaining_seats == 0:
            booking.status = BookingStatus.CANCELLED
            booking.seat_count = 0
            booking.total_price = 0.0
        else:
            booking.seat_count = remaining_seats
            booking.total_price = round(booking.total_price - cancel_gross_price, 2)

        await db.commit()

        return {
            "pnr": booking.pnr,
            "seats_cancelled": payload.seats_to_cancel,
            "remaining_seats": remaining_seats,
            "refund_type": refund_type.value,
            "original_amount": cancel_gross_price,
            "cancellation_fee": cancellation_fee,
            "net_refund_amount": net_refund,
            "currency": booking.currency,
            "status": refund_status.value,
            "travel_credit_code": credit_code,
            "credit_expires_at": credit_expires_at
        }

    @classmethod
    async def process_schedule_change(
        cls, db: AsyncSession, payload: ScheduleChangeRequest
    ) -> Dict[str, Any]:
        """Handles airline-initiated disruptions: auto-rebooks or grants full refund waivers."""
        # Find affected active bookings
        stmt = select(Booking).where(
            Booking.flight_id == payload.flight_id,
            Booking.status == BookingStatus.CONFIRMED
        )
        result = await db.execute(stmt)
        affected_bookings = result.scalars().all()

        is_major_disruption = abs(payload.time_shift_minutes) >= 120
        rebooked_count = 0
        refunded_count = 0

        for booking in affected_bookings:
            if is_major_disruption and not payload.auto_rebook:
                # Issue full involuntary cash refund waiver
                refund = RefundRecord(
                    pnr=booking.pnr,
                    seats_cancelled=booking.seat_count,
                    original_total=booking.total_price,
                    cancellation_fee=0.0, # Zero fee for schedule change
                    net_refund_amount=booking.total_price,
                    currency=booking.currency,
                    refund_type=RefundType.CASH_REFUND,
                    status=RefundStatus.PENDING,
                    reason=f"Airline Schedule Change ({payload.time_shift_minutes}m shift)"
                )
                booking.status = BookingStatus.CANCELLED
                db.add(refund)
                refunded_count += 1
            else:
                # Auto-rebook onto simulated new flight leg
                rebooked_count += 1

        await db.commit()

        return {
            "flight_id": payload.flight_id,
            "affected_pnrs": len(affected_bookings),
            "rebooked_count": rebooked_count,
            "auto_refunded_count": refunded_count,
            "message": f"Processed schedule change. Major disruption: {is_major_disruption}"
        }

    @classmethod
    async def get_stuck_refunds(cls, db: AsyncSession, threshold_days: int = 3) -> List[Dict[str, Any]]:
        """Queries pending refunds open longer than N days and flags them for n8n escalation."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=threshold_days)

        stmt = select(RefundRecord).where(
            RefundRecord.status == RefundStatus.PENDING,
            RefundRecord.created_at <= cutoff_date
        )
        result = await db.execute(stmt)
        stuck_records = result.scalars().all()

        stuck_list = []
        for record in stuck_records:
            # Mark as escalated in DB
            record.is_escalated = True
            record.status = RefundStatus.ESCALATED
            days_pending = (datetime.now(timezone.utc) - record.created_at).days

            stuck_list.append({
                "refund_id": record.id,
                "pnr": record.pnr,
                "refund_type": record.refund_type.value,
                "net_refund_amount": record.net_refund_amount,
                "currency": record.currency,
                "status": record.status.value,
                "days_pending": days_pending,
                "created_at": record.created_at,
                "is_escalated": True
            })

        await db.commit()
        return stuck_list