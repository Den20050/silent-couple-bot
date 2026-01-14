"""Pay router registration."""

from aiogram import Router

from src.bot.handlers.pay.handlers import payment_handlers

router = Router(name="pay")

# Register sub-routers
router.include_router(payment_handlers.router)

