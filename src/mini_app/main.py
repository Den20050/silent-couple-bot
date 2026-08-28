"""Mini App FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from src.core.bootstrap import bootstrap
from src.core.config import settings
from src.core.di.providers.storage import provide_session_factory
from src.core.logger import configure_logging, get_logger
from src.mini_app.routes import router
from src.mini_app.api import set_api_runtime
from src.bot.handlers.webhook import webhook_router
from src.services.telegram import set_bot
from src.services.telegram.bot_factory import create_bot

logger = get_logger(__name__)

configure_logging(
    log_level=settings.log_level,
    log_file=settings.log_file,
    log_file_max_bytes=settings.log_file_max_bytes,
    log_file_backup_count=settings.log_file_backup_count,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = await bootstrap()
    bot = create_bot(settings.tg_bot_token, proxy_url=settings.telegram_proxy_url)
    set_bot(bot)
    container.bot_provider.set_bot(bot)

    session_factory = provide_session_factory(settings)
    set_api_runtime(session_factory=session_factory, container=container)
    app.state.container = container
    app.state.session_factory = session_factory

    logger.info("Mini App started", environment=settings.environment)
    yield

    await container.close()
    await bot.session.close()
    logger.info("Mini App stopped")


app = FastAPI(title="Silent Couple Bot Mini App", lifespan=lifespan)

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

