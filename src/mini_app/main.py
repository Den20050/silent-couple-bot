"""Mini App FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from src.mini_app.routes import router
from src.bot.handlers.webhook import webhook_router

logger = get_logger(__name__)

# Configure logging
configure_logging(
    log_level=settings.log_level,
    log_file=settings.log_file,
    log_file_max_bytes=settings.log_file_max_bytes,
    log_file_backup_count=settings.log_file_backup_count,
)

# Create FastAPI app
app = FastAPI(title="Silent Couple Bot Mini App")

# CORS middleware (for development)
if settings.is_development:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include routes
app.include_router(router)
app.include_router(webhook_router)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup() -> None:
    """Startup event."""
    logger.info("Mini App starting", environment=settings.environment)


@app.on_event("shutdown")
async def shutdown() -> None:
    """Shutdown event."""
    logger.info("Mini App shutting down")

