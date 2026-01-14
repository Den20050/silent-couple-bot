"""Feedback router registration."""

from aiogram import Router

from src.bot.handlers.feedback.handlers import feedback_handlers

router = Router(name="feedback")

# Register sub-routers
router.include_router(feedback_handlers.router)

