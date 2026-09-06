from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.refund import (
    CancellationRequest,
    CancellationResponse,
    ScheduleChangeRequest,
    ScheduleChangeSummary,
    StuckRefundItem
)
from app.services.refund_service import RefundService

router = APIRouter(prefix="/refunds", tags=["Changes, Cancellations & Refunds"])

@router.post("/cancel", response_model=CancellationResponse, status_code=status.HTTP_200_OK)
async def cancel_booking(
    payload: CancellationRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Process voluntary cancellations with fare-rule policy branching and partial passenger seat support."""
    return await RefundService.process_cancellation(db=db, payload=payload)

@router.post("/schedule-change", response_model=ScheduleChangeSummary, status_code=status.HTTP_200_OK)
async def handle_schedule_change(
    payload: ScheduleChangeRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Handle airline-initiated schedule changes, auto-rebooking, and involuntary refund waivers."""
    return await RefundService.process_schedule_change(db=db, payload=payload)

@router.get("/stuck-escalations", response_model=List[StuckRefundItem], status_code=status.HTTP_200_OK)
async def get_stuck_refunds_for_n8n(
    days: int = Query(default=3, ge=1, description="Threshold in days for pending refunds"),
    db: AsyncSession = Depends(get_db_session)
):
    """Exposes pending refunds stuck for > N days for n8n escalation workflows."""
    return await RefundService.get_stuck_refunds(db=db, threshold_days=days)