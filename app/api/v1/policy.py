from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db_session
from app.schemas.policy import PolicyEvaluationRequest, PolicyEvaluationResponse, ResolveApprovalRequest
from app.services.policy_service import PolicyService

router = APIRouter(prefix="/policy", tags=["Approval & Autonomy Matrix"])

@router.post("/evaluate", response_model=PolicyEvaluationResponse, status_code=status.HTTP_200_OK)
async def evaluate_action(
    payload: PolicyEvaluationRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    n8n and internal services call this BEFORE executing sensitive actions.
    Returns whether the system can proceed autonomously or must halt for a human.
    """
    return await PolicyService.evaluate_action(db=db, payload=payload)

@router.post("/approvals/{approval_id}/resolve", status_code=status.HTTP_200_OK)
async def resolve_human_approval(
    approval_id: int,
    payload: ResolveApprovalRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Human agents use the admin dashboard to approve/reject escalated actions."""
    return await PolicyService.resolve_approval(db=db, approval_id=approval_id, payload=payload)