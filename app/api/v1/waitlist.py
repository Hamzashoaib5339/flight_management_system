from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.waitlist import (
    JoinWaitlistRequest,
    WaitlistEntryResponse,
    ProcessPromotionsRequest,
    PromotionResult,
    ClaimSeatRequest
)
from app.services.waitlist_service import WaitlistService

router = APIRouter(prefix="/waitlist", tags=["Waitlist & Standby Engine"])

@router.post("/join", response_model=WaitlistEntryResponse, status_code=status.HTTP_201_CREATED)
async def join_waitlist(
    payload: JoinWaitlistRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Join a flight waitlist with calculated tier and fare class priority scoring."""
    return await WaitlistService.join_waitlist(db=db, payload=payload)

@router.post("/process-promotions", response_model=PromotionResult, status_code=status.HTTP_200_OK)
async def process_freed_seats(
    payload: ProcessPromotionsRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Polls freed seats and atomically promotes top waitlist candidates using DB row locks.
    Ideal endpoint for n8n cron polling.
    """
    return await WaitlistService.process_freed_seats_and_promote(db=db, payload=payload)

@router.post("/claim", status_code=status.HTTP_200_OK)
async def claim_promoted_seat(
    payload: ClaimSeatRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Allows passengers to claim a promoted waitlist seat within the designated expiration window."""
    return await WaitlistService.claim_promoted_seat(db=db, payload=payload)