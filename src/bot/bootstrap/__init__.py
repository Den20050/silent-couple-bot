"""Bot bootstrap module."""

from src.bot.bootstrap.bot_factory import create_bot_and_dispatcher
from src.bot.bootstrap.middleware_setup import setup_middlewares
from src.bot.bootstrap.router_registry import register_routers

__all__ = [
    "create_bot_and_dispatcher",
    "setup_middlewares",
    "register_routers",
]

