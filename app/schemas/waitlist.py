from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class LoyaltyTierEnum(str, Enum):
    PLATINUM = "PLATINUM"
    GOLD = "GOLD"
    SILVER = "SILVER"
    BASE = "BASE"

class JoinWaitlistRequest(BaseModel):
    pnr: str = Field(..., min_length=6, max_length=6, example="AB12CD")
    flight_id: str = Field(..., example="FL-101")
    fare_class: str = Field(..., example="BUSINESS")
    loyalty_tier: LoyaltyTierEnum = LoyaltyTierEnum.BASE

class WaitlistEntryResponse(BaseModel):
    id: int
    pnr: str
    flight_id: str
    fare_class: str
    loyalty_tier: str
    priority_score: int
    status: str
    claim_expires_at: Optional[datetime] = None
    created_at: datetime

class ProcessPromotionsRequest(BaseModel):
    flight_id: str = Field(..., example="FL-101")
    fare_class: str = Field(..., example="BUSINESS")
    claim_window_minutes: int = Field(15, ge=5, le=120, description="Minutes passenger has to claim promoted seat")

class ClaimSeatRequest(BaseModel):
    pnr: str = Field(..., min_length=6, max_length=6)
    waitlist_id: int

class PromotionResult(BaseModel):
    promoted_count: int
    expired_count: int
    promoted_entries: List[WaitlistEntryResponse]
    message: str