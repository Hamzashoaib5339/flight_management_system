import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    DRAFTED = "DRAFTED"
    APPROVED = "APPROVED"
    SENT = "SENT"

class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pnr: Mapped[str] = mapped_column(String(6), index=True, nullable=False)
    customer_email: Mapped[str] = mapped_column(String(100), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    ai_drafted_response: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[TicketStatus] = mapped_column(SQLEnum(TicketStatus), default=TicketStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )