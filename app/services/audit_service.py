import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.core.security import AuthUser

async def write_audit_log(
    db: AsyncSession,
    actor: AuthUser,
    action: str,
    entity: str,
    target_id: uuid.UUID,
    payload: dict[str, Any]
):
    log = AuditLog(
        actor_id=actor.id,
        actor_role=actor.role.value,
        action=action,
        target_entity=entity,
        target_id=target_id,
        payload=payload
    )
    db.add(log)