"""Bot handlers."""

from src.bot.handlers import (
    delete,
    link,
    start,
    subscription,
)
from src.bot.handlers.callbacks import router as callbacks
from src.bot.handlers.menu import router as menu
from src.bot.handlers.pay import router as pay
from src.bot.handlers.settings import router as settings
from src.bot.handlers.admin import router as admin
from src.bot.handlers.feedback import router as feedback

__all__ = [
    "admin",
    "callbacks",
    "delete",
    "feedback",
    "link",
    "menu",
    "pay",
    "settings",
    "start",
    "subscription",
]
