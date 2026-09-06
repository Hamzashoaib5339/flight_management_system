import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, Boolean, Text, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class ActionCategory(str, enum.Enum):
    STANDARD_REFUND = "STANDARD_REFUND"
    DENIED_BOARDING_COMP = "DENIED_BOARDING_COMP"
    SCHEDULE_CHANGE_COMP = "SCHEDULE_CHANGE_COMP"
    PASSENGER_REMINDER = "PASSENGER_REMINDER"
    WAITLIST_PROMOTION = "WAITLIST_PROMOTION"

class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class PolicyAuditLog(Base):
    """Immutable ledger for regulatory reviews."""
    __tablename__ = "policy_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pnr: Mapped[str] = mapped_column(String(6), index=True, nullable=False)
    action_category: Mapped[ActionCategory] = mapped_column(SQLEnum(ActionCategory), nullable=False)
    is_automated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., "AUTO_APPROVED", "REJECTED_BY_HUMAN"
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    context_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    human_agent_id: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

class ApprovalRequest(Base):
    """Queue for actions exceeding automation boundaries."""
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pnr: Mapped[str] = mapped_column(String(6), index=True, nullable=False)
    action_category: Mapped[ActionCategory] = mapped_column(SQLEnum(ActionCategory), nullable=False)
    requested_amount: Mapped[float] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    reviewer_notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)