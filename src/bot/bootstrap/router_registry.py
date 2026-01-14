"""Router registration for bot application."""

from aiogram import Dispatcher

from src.core.logger import get_logger
from src.bot.handlers.admin import router as admin_router
from src.bot.handlers.menu import router as menu_router
from src.bot.handlers.start import router as start_router
from src.bot.handlers.settings import router as settings_router
from src.bot.handlers.subscription import router as subscription_router
from src.bot.handlers.pay import router as pay_router
from src.bot.handlers.feedback import router as feedback_router
from src.bot.handlers.delete import router as delete_router
from src.bot.handlers.link import router as link_router
from src.bot.handlers.callbacks import router as callbacks_router

logger = get_logger(__name__)


def register_routers(dp: Dispatcher) -> None:
    """Register all routers in dispatcher.

    Router order matters:
    1. Commands should be registered FIRST so they are processed before FSM state handlers
    2. FSM state handlers should be registered BEFORE general message handlers
    3. General message handlers should be registered LAST

    Args:
        dp: Dispatcher instance
    """
    # 1. Commands (e.g., /create_pair) - register FIRST
    dp.include_router(admin_router)
    dp.include_router(menu_router)
    
    # 2. FSM state handlers - register BEFORE general message handlers
    # IMPORTANT: FSM state handlers must be registered BEFORE general text handlers
    # to ensure FSM-filtered handlers have priority
    dp.include_router(settings_router)  # Has SettingsStates handlers
    dp.include_router(feedback_router)  # Has FeedbackStates handlers - register BEFORE start_router
    dp.include_router(start_router)  # Has PairCreationStates handlers
    
    # 3. Other handlers
    dp.include_router(subscription_router)
    dp.include_router(pay_router)
    
    # 5. Other handlers
    dp.include_router(delete_router)
    dp.include_router(link_router)
    dp.include_router(callbacks_router)
    
    logger.info("Routers registered", router_count=9)

