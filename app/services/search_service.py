import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from app.schemas.search import FareClassEnum, FareRuleDetails

# Business rules mapping
FARE_RULES_MAP: Dict[FareClassEnum, FareRuleDetails] = {
    FareClassEnum.BASIC_ECONOMY: FareRuleDetails(
        seat_selection_allowed=False,
        changes_allowed=False,
        cancellation_fee_pct=100.0,
        price_hold_duration_minutes=5
    ),
    FareClassEnum.FLEXIBLE: FareRuleDetails(
        seat_selection_allowed=True,
        changes_allowed=True,
        cancellation_fee_pct=0.0,
        price_hold_duration_minutes=15
    ),
    FareClassEnum.BUSINESS: FareRuleDetails(
        seat_selection_allowed=True,
        changes_allowed=True,
        cancellation_fee_pct=0.0,
        price_hold_duration_minutes=30
    )
}

CURRENCY_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "PKR": 278.5
}

# Temporary in-memory hold cache (swap for Redis/DB in production)
ACTIVE_HOLDS: Dict[str, Dict[str, Any]] = {}

class SearchService:
    @staticmethod
    def get_fare_rules(fare_class: FareClassEnum) -> FareRuleDetails:
        return FARE_RULES_MAP[fare_class]

    @classmethod
    def execute_search(
        cls, db_session, legs: List[Any], fare_class: FareClassEnum, currency: str
    ) -> Dict[str, Any]:
        rate = CURRENCY_RATES.get(currency.upper(), 1.0)
        itinerary_results = []
        total_price = 0.0

        # Replace this mockup logic with your SQLAlchemy DB query on models.flight.Flight
        for leg in legs:
            # Simulated flight availability check
            base_price = 350.0 if fare_class == FareClassEnum.BASIC_ECONOMY else 520.0
            converted_price = round(base_price * rate, 2)
            
            itinerary_results.append({
                "flight_id": f"FL-{leg.origin}{leg.destination}",
                "origin": leg.origin,
                "destination": leg.destination,
                "date": leg.flight_date,
                "available_seats": 8,  # Dynamic seat count from DB
                "price": converted_price
            })
            total_price += converted_price

        rules = cls.get_fare_rules(fare_class)

        return {
            "available": True,
            "currency": currency.upper(),
            "total_price": round(total_price, 2),
            "rules": rules,
            "itinerary": itinerary_results
        }

    @classmethod
    def create_price_hold(cls, fare_class: FareClassEnum, locked_price: float, currency: str) -> Dict[str, Any]:
        rules = cls.get_fare_rules(fare_class)
        token = f"HOLD-{secrets.token_hex(8).upper()}"
        expires_at = datetime.utcnow() + timedelta(minutes=rules.price_hold_duration_minutes)

        hold_payload = {
            "hold_token": token,
            "expires_at": expires_at,
            "locked_price": locked_price,
            "currency": currency,
            "fare_class": fare_class
        }
        ACTIVE_HOLDS[token] = hold_payload
        return hold_payload

    @classmethod
    def validate_hold_token(cls, token: str) -> Dict[str, Any]:
        hold = ACTIVE_HOLDS.get(token)
        if not hold:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Price hold token not found or invalid."
            )
        if datetime.utcnow() > hold["expires_at"]:
            del ACTIVE_HOLDS[token]
            raise HTTPException(
                status_code=status.HTTP_410_GONE, 
                detail="Price hold has expired. Please run a new search."
            )
        return hold