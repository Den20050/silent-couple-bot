"""Payment service providers."""

from typing import Optional

from redis.asyncio import Redis

from src.core.config import Settings
from src.services.payment.robokassa_service import RobokassaService
from src.services.payment.webhook_handler import RobokassaWebhookHandler
from src.services.payment.currency_rates import CurrencyRatesService
from src.core.protocols.payment import PaymentServiceProtocol


def provide_payment_service(
    redis: Optional[Redis],
    settings: Settings,
) -> PaymentServiceProtocol:
    """Provide payment service.

    Args:
        redis: Redis client instance
        settings: Application settings

    Returns:
        RobokassaService instance
    """
    return RobokassaService(redis=redis, settings=settings)


def provide_webhook_handler(
    redis: Optional[Redis],
    settings: Settings,
) -> RobokassaWebhookHandler:
    """Provide webhook handler.

    Args:
        redis: Redis client instance
        settings: Application settings

    Returns:
        RobokassaWebhookHandler instance
    """
    return RobokassaWebhookHandler(redis=redis, settings=settings)


def provide_currency_rates_service(
    redis: Optional[Redis],
    settings: Settings,
) -> CurrencyRatesService:
    """Provide currency rates service.

    Args:
        redis: Redis client instance for caching
        settings: Application settings

    Returns:
        CurrencyRatesService instance
    """
    return CurrencyRatesService(redis=redis, settings=settings)

