from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session  # <-- Updated import
from app.schemas.search import (
    SearchQueryRequest, 
    SearchResponse, 
    PriceHoldRequest, 
    PriceHoldResponse
)
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search & Fare Rules"])

CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "PKR": "Rs "
}

@router.post("", response_model=SearchResponse)
async def search_flights(payload: SearchQueryRequest, db: AsyncSession = Depends(get_db_session)): # <-- async def & AsyncSession
    """Search multi-leg flight availability, seat count per class, and fare rules."""
    
    # In the future, if execute_search does DB calls, you will need to `await` it. 
    # For now, it's synchronous mockup logic.
    result = SearchService.execute_search(
        db_session=db, 
        legs=payload.legs, 
        fare_class=payload.fare_class, 
        currency=payload.currency
    )

    symbol = CURRENCY_SYMBOLS.get(payload.currency.upper(), f"{payload.currency.upper()} ")
    formatted_price = f"{symbol}{result['total_price']:,.2f}"

    return {
        **result,
        "formatted_total_price": formatted_price
    }

@router.post("/hold", response_model=PriceHoldResponse)
async def lock_fare_price(payload: PriceHoldRequest, db: AsyncSession = Depends(get_db_session)): # <-- async def & AsyncSession
    """Lock search prices for a fixed duration before booking confirmation."""
    search_res = SearchService.execute_search(
        db_session=db,
        legs=payload.legs,
        fare_class=payload.fare_class,
        currency=payload.currency
    )

    if not search_res.get("available"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fare availability changed mid-booking. Refresh your search."
        )

    hold = SearchService.create_price_hold(
        fare_class=payload.fare_class,
        locked_price=search_res["total_price"],
        currency=payload.currency
    )
    return hold