"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.api_router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.middleware import (
    global_exception_handler,
    http_exception_handler,
    setup_middleware,
    HTTPException as CustomHTTPException,
)
from app.db.session import close_db, engine
from app.db.base import Base
from app.utils.constants import API_V1_PREFIX

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_logging()
    logger.info("application_starting", environment=settings.ENVIRONMENT)
    
    # Create tables (for development - use Alembic in production)
    if settings.DEBUG:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    # Initialize database with default data
    from app.db.session import async_session_factory
    from app.db.init_db import init_database
    async with async_session_factory() as session:
        await init_database(session)
    
    logger.info("application_started")
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    await close_db()
    logger.info("application_stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Medical Tourism Platform API",
    openapi_url=f"{API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Setup middleware
setup_middleware(app)

# Exception handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(CustomHTTPException, http_exception_handler)

# Include API router
app.include_router(api_router, prefix=API_V1_PREFIX)


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api", tags=["Health"])
async def api_info():
    """API information endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "api_version": "v1",
        "docs_url": "/docs",
        "openapi_url": f"{API_V1_PREFIX}/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
