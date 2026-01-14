"""Admin router registration."""

from aiogram import Router

from src.bot.handlers.admin.handlers import admin_commands

router = Router(name="admin")

# Register sub-routers
router.include_router(admin_commands.router)

