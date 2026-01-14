"""Application service providers."""

from typing import Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.protocols.bot_provider import BotProviderProtocol
from src.core.protocols.payment import PaymentServiceProtocol
from src.domain.services.pair_onboarding import PairOnboardingService
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.application.admin import AdminApplicationService
from src.services.application.menu import MenuApplicationService
from src.services.application.pair import PairApplicationService
from src.services.application.payment import PaymentApplicationService
from src.services.application.settings import SettingsApplicationService
from src.services.application.subscription import SubscriptionApplicationService
from src.services.messaging.ui.admin_ui import AdminUIService
from src.services.messaging.ui.menu_ui import MenuUIService
from src.services.messaging.ui.payment_ui import PaymentUIService
from src.services.messaging.ui.settings_ui import SettingsUIService
from src.services.payment.currency_rates import CurrencyRatesService


def provide_subscription_application_service(
    session: AsyncSession,
    subscription_status_service: SubscriptionStatusService,
    menu_ui: MenuUIService,
) -> SubscriptionApplicationService:
    """Provide subscription application service.
    
    Args:
        session: Database session
        subscription_status_service: Domain service for subscription status
        menu_ui: UI service for menu-related messages
        
    Returns:
        SubscriptionApplicationService instance
    """
    return SubscriptionApplicationService(
        session=session,
        subscription_status_service=subscription_status_service,
        menu_ui=menu_ui,
    )


def provide_payment_application_service(
    session: AsyncSession,
    payment_service: PaymentServiceProtocol,
    subscription_status_service: SubscriptionStatusService,
    bot_provider: BotProviderProtocol,
    payment_ui: PaymentUIService,
    settings: Settings,
    currency_rates_service: CurrencyRatesService,
) -> PaymentApplicationService:
    """Provide payment application service.
    
    Args:
        session: Database session
        payment_service: Payment service protocol implementation
        subscription_status_service: Domain service for subscription status
        bot_provider: Bot provider protocol
        payment_ui: UI service for payment-related messages
        settings: Application settings
        currency_rates_service: Currency rates service for dynamic pricing
        
    Returns:
        PaymentApplicationService instance
    """
    return PaymentApplicationService(
        session=session,
        payment_service=payment_service,
        subscription_status_service=subscription_status_service,
        bot_provider=bot_provider,
        payment_ui=payment_ui,
        settings=settings,
        currency_rates_service=currency_rates_service,
    )


def provide_settings_application_service(
    session: AsyncSession,
    subscription_status_service: SubscriptionStatusService,
    settings_ui: SettingsUIService,
) -> SettingsApplicationService:
    """Provide settings application service.
    
    Args:
        session: Database session
        subscription_status_service: Domain service for subscription status
        settings_ui: UI service for settings-related messages
        
    Returns:
        SettingsApplicationService instance
    """
    return SettingsApplicationService(
        session=session,
        subscription_status_service=subscription_status_service,
        settings_ui=settings_ui,
    )


def provide_pair_application_service(
    session: AsyncSession,
    pair_onboarding_service: PairOnboardingService,
) -> PairApplicationService:
    """Provide pair application service.
    
    Args:
        session: Database session
        pair_onboarding_service: Domain service for pair onboarding
        
    Returns:
        PairApplicationService instance
    """
    return PairApplicationService(
        session=session,
        pair_onboarding_service=pair_onboarding_service,
    )


def provide_menu_application_service(
    session: AsyncSession,
    menu_ui: MenuUIService,
) -> MenuApplicationService:
    """Provide menu application service.
    
    Args:
        session: Database session
        menu_ui: UI service for menu-related messages
        
    Returns:
        MenuApplicationService instance
    """
    return MenuApplicationService(
        session=session,
        menu_ui=menu_ui,
    )


def provide_admin_application_service(
    session: AsyncSession,
    admin_ui: AdminUIService,
) -> AdminApplicationService:
    """Provide admin application service.
    
    Args:
        session: Database session
        admin_ui: UI service for admin-related messages
        
    Returns:
        AdminApplicationService instance
    """
    return AdminApplicationService(
        session=session,
        admin_ui=admin_ui,
    )

