from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.fraud import FraudRecord, RiskLevel
from app.schemas.fraud import FraudAnalysisRequest
from app.models.booking import Booking, BookingStatus

class FraudService:
    @classmethod
    async def get_unscored_bookings(cls, db: AsyncSession) -> List[Dict[str, Any]]:
        """Used by n8n batch job to fetch bookings that need fraud analysis."""
        # Finds confirmed bookings without a corresponding fraud record
        stmt = select(Booking).outerjoin(
            FraudRecord, Booking.pnr == FraudRecord.pnr
        ).where(
            FraudRecord.id == None,
            Booking.status == BookingStatus.CONFIRMED
        ).limit(50)
        
        result = await db.execute(stmt)
        bookings = result.scalars().all()
        
        return [{
            "pnr": b.pnr,
            "total_price": b.total_price,
            "created_at": b.created_at.isoformat()
        } for b in bookings]

    @classmethod
    async def save_fraud_analysis(cls, db: AsyncSession, payload: FraudAnalysisRequest):
        level = RiskLevel.LOW
        if payload.risk_score >= 80: level = RiskLevel.CRITICAL
        elif payload.risk_score >= 50: level = RiskLevel.HIGH
        elif payload.risk_score >= 20: level = RiskLevel.MEDIUM

        record = FraudRecord(
            pnr=payload.pnr,
            risk_score=payload.risk_score,
            risk_level=level,
            fraud_flags=payload.fraud_flags
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record