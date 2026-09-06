from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db_session
from app.schemas.fraud import FraudAnalysisRequest, FraudRecordResponse
from app.services.fraud_service import FraudService

router = APIRouter(prefix="/fraud", tags=["Fraud Detection Engine"])

@router.get("/pending", status_code=status.HTTP_200_OK)
async def get_pending_bookings(db: AsyncSession = Depends(get_db_session)):
    """n8n polls this to get bookings missing a fraud score."""
    return await FraudService.get_unscored_bookings(db)

@router.post("/score", response_model=FraudRecordResponse, status_code=status.HTTP_201_CREATED)
async def submit_fraud_score(payload: FraudAnalysisRequest, db: AsyncSession = Depends(get_db_session)):
    """n8n posts the calculated ML/Rule-based fraud score here."""
    return await FraudService.save_fraud_analysis(db, payload)