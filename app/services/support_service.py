from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.support import SupportTicket, TicketStatus

class SupportService:
    @classmethod
    async def create_draft_ticket(
        cls, 
        db: AsyncSession, 
        pnr: str, 
        customer_email: str, 
        query_text: str, 
        ai_drafted_response: str
    ):
        ticket = SupportTicket(
            pnr=pnr,
            customer_email=customer_email,
            query_text=query_text,
            ai_drafted_response=ai_drafted_response,
            status=TicketStatus.DRAFTED
        )
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @classmethod
    async def update_ticket_status(
        cls, 
        db: AsyncSession, 
        ticket_id: int, 
        new_status: TicketStatus
    ):
        stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
        ticket = (await db.execute(stmt)).scalars().first()
        
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")
            
        ticket.status = new_status
        await db.commit()
        await db.refresh(ticket)
        return ticket