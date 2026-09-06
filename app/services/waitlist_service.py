from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, update

from app.models.waitlist import WaitlistEntry, WaitlistStatus, LoyaltyTier
from app.models.booking import Booking, BookingStatus
from app.models.flight import Flight
from app.schemas.waitlist import JoinWaitlistRequest, ProcessPromotionsRequest, ClaimSeatRequest

# Priority Weights
TIER_WEIGHTS = {
    LoyaltyTier.PLATINUM: 1000,
    LoyaltyTier.GOLD: 500,
    LoyaltyTier.SILVER: 200,
    LoyaltyTier.BASE: 50
}

FARE_CLASS_WEIGHTS = {
    "BUSINESS": 300,
    "FLEXIBLE": 150,
    "BASIC_ECONOMY": 50
}

class WaitlistService:

    @classmethod
    def calculate_priority_score(cls, tier: LoyaltyTier, fare_class: str) -> int:
        tier_score = TIER_WEIGHTS.get(tier, 50)
        fare_score = FARE_CLASS_WEIGHTS.get(fare_class.upper(), 50)
        return tier_score + fare_score

    @classmethod
    async def _resolve_flight_uuid(cls, db: AsyncSession, flight_id: str):
        """
        WaitlistEntry.flight_id stores the human-readable flight_number
        (e.g. "FL-101"), but Booking.flight_id is a foreign key to the
        real Flight.id UUID. This resolves one to the other so callers
        can keep using the friendly flight_number everywhere.
        """
        flight_stmt = select(Flight).where(Flight.flight_number == flight_id)
        flight = (await db.execute(flight_stmt)).scalars().first()

        if not flight:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flight '{flight_id}' not found."
            )

        return flight.id

    @classmethod
    async def join_waitlist(
        cls, db: AsyncSession, payload: JoinWaitlistRequest
    ) -> WaitlistEntry:

        # Check existing active waitlist entry
        existing_stmt = select(WaitlistEntry).where(
            WaitlistEntry.pnr == payload.pnr,
            WaitlistEntry.flight_id == payload.flight_id,
            WaitlistEntry.status.in_([WaitlistStatus.WAITING, WaitlistStatus.PROMOTED])
        )
        existing = (await db.execute(existing_stmt)).scalars().first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"PNR {payload.pnr} is already on the waitlist with status {existing.status.value}."
            )

        score = cls.calculate_priority_score(payload.loyalty_tier, payload.fare_class)

        entry = WaitlistEntry(
            pnr=payload.pnr,
            flight_id=payload.flight_id,
            fare_class=payload.fare_class.upper(),
            loyalty_tier=payload.loyalty_tier,
            priority_score=score,
            status=WaitlistStatus.WAITING
        )

        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    @classmethod
    async def process_freed_seats_and_promote(
        cls, db: AsyncSession, payload: ProcessPromotionsRequest
    ) -> Dict[str, Any]:
        """
        Concurrency-protected promotion loop using row-locking (FOR UPDATE).
        Prevents race conditions between n8n background jobs and gate agents.
        """
        now = datetime.now(timezone.utc)

        # 0. Resolve the human-readable flight_id ("FL-101") to the real
        #    Flight.id UUID that Booking.flight_id actually stores.
        flight_uuid = await cls._resolve_flight_uuid(db, payload.flight_id)

        # 1. Expire past due promotions first
        expire_stmt = select(WaitlistEntry).where(
            WaitlistEntry.flight_id == payload.flight_id,
            WaitlistEntry.status == WaitlistStatus.PROMOTED,
            WaitlistEntry.claim_expires_at < now
        ).with_for_update()

        expired_result = await db.execute(expire_stmt)
        expired_entries = expired_result.scalars().all()

        expired_count = len(expired_entries)
        for entry in expired_entries:
            entry.status = WaitlistStatus.EXPIRED

        # 2. Count current active confirmed/held seats (Booking uses the real UUID FK)
        active_bookings_stmt = select(func.coalesce(func.sum(Booking.seat_count), 0)).where(
            Booking.flight_id == flight_uuid,
            Booking.fare_class == payload.fare_class,
            Booking.status.in_([BookingStatus.HELD, BookingStatus.CONFIRMED]),
            Booking.expires_at > now
        ).with_for_update()

        occupied_seats = (await db.execute(active_bookings_stmt)).scalar_one()

        # Simulated Class Total Capacity (Replace with dynamic model lookup as needed)
        CLASS_CAPACITY = 20
        available_seats = max(0, CLASS_CAPACITY - occupied_seats)

        if available_seats <= 0:
            await db.commit()
            return {
                "promoted_count": 0,
                "expired_count": expired_count,
                "promoted_entries": [],
                "message": "No available seats to promote waitlisted passengers."
            }

        # 3. Lock candidate waitlist entries in strict priority order
        #    (WaitlistEntry.flight_id stays as the human-readable flight_id)
        waitlist_stmt = select(WaitlistEntry).where(
            WaitlistEntry.flight_id == payload.flight_id,
            WaitlistEntry.fare_class == payload.fare_class.upper(),
            WaitlistEntry.status == WaitlistStatus.WAITING
        ).order_by(
            desc(WaitlistEntry.priority_score),
            asc(WaitlistEntry.created_at)
        ).limit(available_seats).with_for_update()

        candidates = (await db.execute(waitlist_stmt)).scalars().all()

        promoted_list = []
        claim_deadline = now + timedelta(minutes=payload.claim_window_minutes)

        for candidate in candidates:
            candidate.status = WaitlistStatus.PROMOTED
            candidate.claim_expires_at = claim_deadline
            promoted_list.append(candidate)

        await db.commit()

        return {
            "promoted_count": len(promoted_list),
            "expired_count": expired_count,
            "promoted_entries": promoted_list,
            "message": f"Promoted {len(promoted_list)} waitlisted passenger(s)."
        }

    @classmethod
    async def claim_promoted_seat(
        cls, db: AsyncSession, payload: ClaimSeatRequest
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)

        stmt = select(WaitlistEntry).where(
            WaitlistEntry.id == payload.waitlist_id,
            WaitlistEntry.pnr == payload.pnr
        ).with_for_update()

        entry = (await db.execute(stmt)).scalars().first()

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Waitlist record not found."
            )

        if entry.status != WaitlistStatus.PROMOTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot claim seat. Waitlist status is {entry.status.value}."
            )

        if entry.claim_expires_at and entry.claim_expires_at < now:
            entry.status = WaitlistStatus.EXPIRED
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Seat claim window has expired."
            )

        # Transition status to CLAIMED
        entry.status = WaitlistStatus.CLAIMED

        # Convert/Confirm associated Booking row
        booking_stmt = select(Booking).where(Booking.pnr == payload.pnr).with_for_update()
        booking = (await db.execute(booking_stmt)).scalars().first()
        if booking:
            booking.status = BookingStatus.CONFIRMED

        await db.commit()

        return {
            "pnr": entry.pnr,
            "flight_id": entry.flight_id,
            "fare_class": entry.fare_class,
            "status": "CONFIRMED",
            "message": "Promoted seat successfully claimed and booking confirmed."
        }