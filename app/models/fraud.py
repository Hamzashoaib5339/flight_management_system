import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class FraudRecord(Base):
    __tablename__ = "fraud_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pnr: Mapped[str] = mapped_column(String(6), unique=True, index=True, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(SQLEnum(RiskLevel), default=RiskLevel.LOW)
    fraud_flags: Mapped[list] = mapped_column(JSON, nullable=True) # List of string flags
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )