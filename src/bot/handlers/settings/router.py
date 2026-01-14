"""Settings router registration."""

from aiogram import Router

from src.bot.handlers.settings.handlers import settings_handlers

router = Router(name="settings")

# Register sub-routers
router.include_router(settings_handlers.router)

