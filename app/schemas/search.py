from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import List, Optional
from enum import Enum

class FareClassEnum(str, Enum):
    BASIC_ECONOMY = "BASIC_ECONOMY"
    FLEXIBLE = "FLEXIBLE"
    BUSINESS = "BUSINESS"

class LegSearchRequest(BaseModel):
    origin: str = Field(..., example="JFK")
    destination: str = Field(..., example="LHR")
    flight_date: date

class SearchQueryRequest(BaseModel):
    legs: List[LegSearchRequest]
    fare_class: FareClassEnum = FareClassEnum.BASIC_ECONOMY
    currency: str = Field(default="USD", max_length=3)
    locale: str = Field(default="en-US")

class FareRuleDetails(BaseModel):
    seat_selection_allowed: bool
    changes_allowed: bool
    cancellation_fee_pct: float
    price_hold_duration_minutes: int

class LegSearchResult(BaseModel):
    flight_id: str
    origin: str
    destination: str
    date: date
    available_seats: int
    price: float

class SearchResponse(BaseModel):
    available: bool
    currency: str
    total_price: float
    formatted_total_price: str
    rules: FareRuleDetails
    itinerary: List[LegSearchResult]

class PriceHoldRequest(BaseModel):
    legs: List[LegSearchRequest]
    fare_class: FareClassEnum
    currency: str = "USD"

class PriceHoldResponse(BaseModel):
    hold_token: str
    expires_at: datetime
    locked_price: float
    currency: str