"""Callback router registration."""

from aiogram import Router

from src.bot.handlers.callbacks.handlers import (
    evening_requests,
    morning_requests,
    other,
    responses,
)

router = Router(name="callbacks")

# Register sub-routers
router.include_router(morning_requests.router)
router.include_router(evening_requests.router)
router.include_router(responses.router)
router.include_router(other.router)
