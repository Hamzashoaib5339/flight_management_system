import uuid
from enum import Enum
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

class Role(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    OPS_AGENT = "OPS_AGENT"

security = HTTPBearer()

class AuthUser(BaseModel):
    id: uuid.UUID
    role: Role

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthUser:
    # Replace with JWT validation logic
    return AuthUser(id=uuid.UUID("11111111-1111-1111-1111-111111111111"), role=Role.SUPER_ADMIN)

def require_roles(allowed_roles: list[Role]):
    def role_checker(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this operation"
            )
        return user
    return role_checker