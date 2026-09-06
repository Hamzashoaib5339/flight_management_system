from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class FraudAnalysisRequest(BaseModel):
    pnr: str
    risk_score: float
    fraud_flags: List[str]

class FraudRecordResponse(BaseModel):
    pnr: str
    risk_score: float
    risk_level: str
    fraud_flags: List[str]
    analyzed_at: datetime