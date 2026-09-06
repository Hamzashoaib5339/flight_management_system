from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db_session
from app.services.support_service import SupportService
from app.models.support import TicketStatus

router = APIRouter(prefix="/support", tags=["RAG Support & HITL"])

class CreateSupportTicketRequest(BaseModel):
    pnr: str
    customer_email: EmailStr
    query_text: str
    ai_drafted_response: str

@router.post("/tickets", status_code=status.HTTP_201_CREATED)
async def create_ticket(payload: CreateSupportTicketRequest, db: AsyncSession = Depends(get_db_session)):
    """n8n posts the RAG-generated draft here for human approval storage."""
    return await SupportService.create_draft_ticket(
        db, payload.pnr, payload.customer_email, payload.query_text, payload.ai_drafted_response
    )

@router.patch("/tickets/{ticket_id}/status", status_code=status.HTTP_200_OK)
async def update_status(ticket_id: int, new_status: TicketStatus, db: AsyncSession = Depends(get_db_session)):
    """Updates ticket status when human review approves or rejects."""
    return await SupportService.update_ticket_status(db, ticket_id, new_status)