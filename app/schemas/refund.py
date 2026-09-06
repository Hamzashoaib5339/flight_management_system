from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class CancellationRequest(BaseModel):
    pnr: str = Field(..., min_length=6, max_length=6, example="AB12CD")
    seats_to_cancel: int = Field(1, ge=1, description="Number of seats to cancel from this PNR")
    reason: Optional[str] = Field("Customer voluntary cancellation", max_length=255)

class CancellationResponse(BaseModel):
    pnr: str
    seats_cancelled: int
    remaining_seats: int
    refund_type: str
    original_amount: float
    cancellation_fee: float
    net_refund_amount: float
    currency: str
    status: str
    travel_credit_code: Optional[str] = None
    credit_expires_at: Optional[datetime] = None

class ScheduleChangeRequest(BaseModel):
    flight_id: str = Field(..., example="FL-101")
    time_shift_minutes: int = Field(..., example=180, description="Positive for delay, negative for advance")
    new_departure_time: datetime
    auto_rebook: bool = Field(True, description="Attempt auto-rebook on equivalent flights if shift > 120 mins")

class ScheduleChangeSummary(BaseModel):
    flight_id: str
    affected_pnrs: int
    rebooked_count: int
    auto_refunded_count: int
    message: str

class StuckRefundItem(BaseModel):
    refund_id: int
    pnr: str
    refund_type: str
    net_refund_amount: float
    currency: str
    status: str
    days_pending: int
    created_at: datetime
    is_escalated: bool