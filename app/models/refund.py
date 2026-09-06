import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, Boolean, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class RefundStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"

class RefundType(str, enum.Enum):
    CASH_REFUND = "CASH_REFUND"
    TRAVEL_CREDIT = "TRAVEL_CREDIT"
    NON_REFUNDABLE = "NON_REFUNDABLE"

class RefundRecord(Base):
    __tablename__ = "refund_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pnr: Mapped[str] = mapped_column(String(6), index=True, nullable=False)
    seats_cancelled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    original_total: Mapped[float] = mapped_column(Float, nullable=False)
    cancellation_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_refund_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    refund_type: Mapped[RefundType] = mapped_column(SQLEnum(RefundType), nullable=False)
    status: Mapped[RefundStatus] = mapped_column(
        SQLEnum(RefundStatus), nullable=False, default=RefundStatus.PENDING
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=True)
    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

class TravelCredit(Base):
    __tablename__ = "travel_credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credit_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    pnr: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    is_redeemed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)