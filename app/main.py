import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.middleware.request_context import RequestContextMiddleware

configure_logging()
logger = logging.getLogger("app.main")

app = FastAPI(
    title="AI Food Agent",
    description="Personal nutrition assistant backend: profile-aware food image "
    "analysis, water tracking, and AI-generated nutrition recommendations.",
    version="0.1.0",
)

app.add_middleware(RequestContextMiddleware)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["health"], summary="Liveness/readiness probe")
def health_check() -> dict:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("Database health check failed")
        db_ok = False
    finally:
        db.close()

    return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "error"}
