"""Database session middleware."""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger

logger = get_logger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """Middleware to inject database session.

    Uses session_factory from container if available, otherwise falls back
    to direct import for backward compatibility.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Inject database session."""
        # Try to get session_factory from container (if ContainerMiddleware ran first)
        container = data.get("container")
        if container:
            session_factory = container.session_factory
            async with session_factory() as session:
                data["session"] = session
                
                # Inject domain services with session
                from src.domain.services.subscription_status import SubscriptionStatusService
                from src.domain.services.pair_onboarding import PairOnboardingService
                
                subscription_status_service = SubscriptionStatusService(session)
                pair_onboarding_service = PairOnboardingService(session)
                
                data["subscription_status_service"] = subscription_status_service
                data["pair_onboarding_service"] = pair_onboarding_service
                
                # Inject application services (coordinate domain services + repositories + UI)
                from src.core.di.providers.application import (
                    provide_admin_application_service,
                    provide_menu_application_service,
                    provide_pair_application_service,
                    provide_payment_application_service,
                    provide_settings_application_service,
                    provide_subscription_application_service,
                )
                
                # Get UI services from container (already created in ContainerMiddleware)
                menu_ui = data.get("menu_ui")
                payment_ui = data.get("payment_ui")
                settings_ui = data.get("settings_ui")
                admin_ui = data.get("admin_ui")
                
                # Get services from container
                payment_service = data.get("payment_service")
                bot_provider = data.get("bot_provider")
                settings = data.get("settings")
                redis = container.redis if container else None
                
                # Create currency rates service with Redis for caching
                from src.core.di.providers.payment import provide_currency_rates_service
                currency_rates_service = provide_currency_rates_service(
                    redis=redis,
                    settings=settings,
                )
                
                # Create application services
                data["subscription_application_service"] = provide_subscription_application_service(
                    session=session,
                    subscription_status_service=subscription_status_service,
                    menu_ui=menu_ui,
                )
                data["payment_application_service"] = provide_payment_application_service(
                    session=session,
                    payment_service=container.payment_service,
                    subscription_status_service=subscription_status_service,
                    bot_provider=container.bot_provider,
                    payment_ui=payment_ui,
                    settings=container.settings,
                    currency_rates_service=currency_rates_service,
                )
                data["settings_application_service"] = provide_settings_application_service(
                    session=session,
                    subscription_status_service=subscription_status_service,
                    settings_ui=settings_ui,
                )
                data["pair_application_service"] = provide_pair_application_service(
                    session=session,
                    pair_onboarding_service=pair_onboarding_service,
                )
                data["menu_application_service"] = provide_menu_application_service(
                    session=session,
                    menu_ui=menu_ui,
                )
                data["admin_application_service"] = provide_admin_application_service(
                    session=session,
                    admin_ui=admin_ui,
                )
                
                try:
                    result = await handler(event, data)
                    await session.commit()
                    return result
                except Exception as e:
                    logger.error("Handler error", error=str(e), exc_info=True)
                    await session.rollback()
                    raise
        else:
            # Fallback to direct import for backward compatibility
            from src.db.base import async_session_maker

            async with async_session_maker() as session:
                data["session"] = session
                
                # Inject domain services with session
                from src.domain.services.subscription_status import SubscriptionStatusService
                from src.domain.services.pair_onboarding import PairOnboardingService
                
                data["subscription_status_service"] = SubscriptionStatusService(session)
                data["pair_onboarding_service"] = PairOnboardingService(session)
                
                try:
                    result = await handler(event, data)
                    await session.commit()
                    return result
                except Exception as e:
                    logger.error("Handler error", error=str(e), exc_info=True)
                    await session.rollback()
                    raise

