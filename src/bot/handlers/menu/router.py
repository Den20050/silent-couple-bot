"""Menu router registration."""

from aiogram import Router

from src.bot.handlers.menu.handlers import menu_items, admin, admin_actions

router = Router(name="menu")

# Register sub-routers
router.include_router(menu_items.router)
router.include_router(admin.router)
router.include_router(admin_actions.router)

