from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.database import engine
from app.models.base import Base

# Register all model metadata for database table creation
import app.models.flight    # noqa: F401
import app.models.audit     # noqa: F401
import app.models.booking   # noqa: F401
import app.models.refund    # noqa: F401
import app.models.waitlist  # noqa: F401
import app.models.fraud     # noqa: F401
import app.models.support   # noqa: F401
import app.models.policy    # noqa: F401

# Routers
from app.api.v1.admin_flights import router as admin_flights_router
from app.api.v1.search import router as search_router
from app.api.v1.booking import router as booking_router
from app.api.v1.refunds import router as refunds_router
from app.api.v1.waitlist import router as waitlist_router
from app.api.v1.fraud import router as fraud_router
from app.api.support import router as support_router
from app.api.v1.policy import router as policy_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Flight Management System API",
    version="1.0.0",
    lifespan=lifespan,
)

# Include all version 1 routers
app.include_router(admin_flights_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(booking_router, prefix="/api/v1")
app.include_router(refunds_router, prefix="/api/v1")
app.include_router(waitlist_router, prefix="/api/v1")
app.include_router(fraud_router, prefix="/api/v1")
app.include_router(support_router, prefix="/api/v1")
app.include_router(policy_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}