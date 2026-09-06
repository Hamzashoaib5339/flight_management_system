import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class LoyaltyTier(str, enum.Enum):
    PLATINUM = "PLATINUM"
    GOLD = "GOLD"
    SILVER = "SILVER"
    BASE = "BASE"

class WaitlistStatus(str, enum.Enum):
    WAITING = "WAITING"
    PROMOTED = "PROMOTED"
    CLAIMED = "CLAIMED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pnr: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    flight_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    fare_class: Mapped[str] = mapped_column(String(30), nullable=False)
    loyalty_tier: Mapped[LoyaltyTier] = mapped_column(
        SQLEnum(LoyaltyTier), nullable=False, default=LoyaltyTier.BASE
    )
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[WaitlistStatus] = mapped_column(
        SQLEnum(WaitlistStatus), nullable=False, default=WaitlistStatus.WAITING, index=True
    )
    claim_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_waitlist_priority", "flight_id", "status", "priority_score", "created_at"),
    )