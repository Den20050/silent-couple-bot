"""Menu router registration."""

from aiogram import Router

from src.bot.handlers.menu.handlers import admin, admin_actions, menu_items

router = Router(name="menu")

# Register sub-routers
router.include_router(menu_items.router)
router.include_router(admin.router)
router.include_router(admin_actions.router)
