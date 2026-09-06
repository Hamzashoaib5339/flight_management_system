from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.policy import PolicyAuditLog, ApprovalRequest, ActionCategory, ApprovalStatus
from app.schemas.policy import PolicyEvaluationRequest, PolicyEvaluationResponse, ResolveApprovalRequest

# The Policy Matrix Boundary Definitions
AUTO_APPROVE_THRESHOLDS = {
    ActionCategory.STANDARD_REFUND: 500.00,       # Auto-approve refunds under $500
    ActionCategory.DENIED_BOARDING_COMP: 0.0,     # ALWAYS requires human
    ActionCategory.SCHEDULE_CHANGE_COMP: 100.00,  # Auto-approve minor disruption credits
    ActionCategory.PASSENGER_REMINDER: float('inf'), # Always auto-approved
    ActionCategory.WAITLIST_PROMOTION: float('inf')  # Always auto-approved
}

class PolicyService:

    @classmethod
    async def evaluate_action(
        cls, db: AsyncSession, payload: PolicyEvaluationRequest
    ) -> PolicyEvaluationResponse:
        
        threshold = AUTO_APPROVE_THRESHOLDS.get(payload.action_category, 0.0)
        amount = payload.requested_amount or 0.0

        is_auto = amount <= threshold

        if is_auto:
            # 1. Log Automated Action to Audit Trail
            log = PolicyAuditLog(
                pnr=payload.pnr,
                action_category=payload.action_category,
                is_automated=True,
                decision="AUTO_APPROVED",
                justification=f"Amount {amount} is within auto-approve threshold of {threshold}.",
                context_data=payload.context_data
            )
            db.add(log)
            await db.commit()
            
            return PolicyEvaluationResponse(
                pnr=payload.pnr,
                action_category=payload.action_category.value,
                is_auto_approved=True,
                requires_human=False,
                message="Action automatically approved by Policy Matrix."
            )
        else:
            # 2. Route to Human Approval Queue
            req = ApprovalRequest(
                pnr=payload.pnr,
                action_category=payload.action_category,
                requested_amount=amount,
                currency=payload.currency
            )
            db.add(req)
            await db.commit()
            await db.refresh(req)

            # Log the escalation
            log = PolicyAuditLog(
                pnr=payload.pnr,
                action_category=payload.action_category,
                is_automated=True,
                decision="ESCALATED_TO_HUMAN",
                justification=f"Amount {amount} exceeds threshold {threshold} or strict policy requires human.",
                context_data={"approval_request_id": req.id}
            )
            db.add(log)
            await db.commit()

            return PolicyEvaluationResponse(
                pnr=payload.pnr,
                action_category=payload.action_category.value,
                is_auto_approved=False,
                requires_human=True,
                approval_request_id=req.id,
                message="Action requires human approval. Placed in review queue."
            )

    @classmethod
    async def resolve_approval(
        cls, db: AsyncSession, approval_id: int, payload: ResolveApprovalRequest
    ) -> Dict[str, Any]:
        
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        req = (await db.execute(stmt)).scalars().first()

        if not req:
            raise HTTPException(status_code=404, detail="Approval request not found.")
        if req.status != ApprovalStatus.PENDING:
            raise HTTPException(status_code=400, detail=f"Request already resolved: {req.status.value}")

        # Update Request
        req.status = payload.decision
        req.reviewer_notes = payload.reviewer_notes
        req.resolved_at = datetime.now(timezone.utc)

        # Append to Regulatory Audit Trail
        log = PolicyAuditLog(
            pnr=req.pnr,
            action_category=req.action_category,
            is_automated=False,
            decision=f"HUMAN_{payload.decision.value}",
            justification=payload.reviewer_notes,
            human_agent_id=payload.agent_id,
            context_data={"approval_request_id": req.id, "amount": req.requested_amount}
        )
        db.add(log)
        await db.commit()

        return {"status": "success", "decision": payload.decision.value, "pnr": req.pnr}