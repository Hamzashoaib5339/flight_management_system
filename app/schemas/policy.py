from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.policy import ActionCategory, ApprovalStatus

class PolicyEvaluationRequest(BaseModel):
    pnr: str = Field(..., min_length=6, max_length=6)
    action_category: ActionCategory
    requested_amount: Optional[float] = 0.0
    currency: Optional[str] = "USD"
    context_data: Optional[Dict[str, Any]] = {}

class PolicyEvaluationResponse(BaseModel):
    pnr: str
    action_category: str
    is_auto_approved: bool
    requires_human: bool
    approval_request_id: Optional[int] = None
    message: str

class ResolveApprovalRequest(BaseModel):
    agent_id: str = Field(..., description="Email or ID of the human reviewer")
    decision: ApprovalStatus
    reviewer_notes: str = Field(..., min_length=10)