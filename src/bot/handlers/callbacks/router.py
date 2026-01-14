"""Callback router registration."""

from aiogram import Router

from src.bot.handlers.callbacks.handlers import (
    morning_requests,
    evening_requests,
    responses,
    other,
)

router = Router(name="callbacks")

# Register sub-routers
router.include_router(morning_requests.router)
router.include_router(evening_requests.router)
router.include_router(responses.router)
router.include_router(other.router)

