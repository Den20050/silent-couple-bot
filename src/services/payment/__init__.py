"""Payment service module with circuit breaker and provider support.

This module provides:
- CircuitBreaker: Universal circuit breaker for external services
- PaymentProvider: Abstract interface for payment providers
- RobokassaService: Robokassa payment provider implementation
- RobokassaWebhookHandler: Handler for Robokassa webhooks
- PaymentService: Backward compatibility wrapper

For backward compatibility, the module exports PaymentService class
that maintains the same interface as the original payment.py module.
"""

from typing import Optional

from redis.asyncio import Redis

from src.core.config import Settings
from src.services.payment.circuit_breaker import CircuitBreaker
from src.services.payment.interfaces import PaymentProvider
from src.services.payment.robokassa_service import RobokassaService
from src.services.payment.webhook_handler import RobokassaWebhookHandler

# Export for backward compatibility and new code
__all__ = [
    # Circuit breaker
    "CircuitBreaker",
    # Interfaces
    "PaymentProvider",
    # Providers
    "RobokassaService",
    # Webhook handlers
    "RobokassaWebhookHandler",
    # Backward compatibility
    "PaymentService",
]


class PaymentService:
    """Payment service (backward compatibility wrapper).

    This class maintains backward compatibility with the original PaymentService.
    Internally uses RobokassaService and RobokassaWebhookHandler.

    For new code, prefer using RobokassaService and RobokassaWebhookHandler directly.
    """

    def __init__(self, redis: Redis | None, settings: Settings) -> None:
        """Initialize payment service.

        Args:
            redis: Redis client for circuit breaker (optional)
            settings: Application settings (required)
        """
        self.redis = redis
        self._robokassa_service = RobokassaService(redis=redis, settings=settings)
        self._webhook_handler = RobokassaWebhookHandler(redis=redis, settings=settings)
        # Expose circuit_breaker for backward compatibility
        self.circuit_breaker = self._robokassa_service.circuit_breaker
    
    async def create_payment(
        self,
        amount: int,
        pair_id: int,
        return_url: str,
        period_days: int = 30,
        is_lifetime: bool = False,
        currency: str = "RUB",
    ):
        """Create payment link (backward compatibility).
        
        Delegates to RobokassaService.create_payment.
        """
        return await self._robokassa_service.create_payment(
            amount=amount,
            pair_id=pair_id,
            return_url=return_url,
            period_days=period_days,
            is_lifetime=is_lifetime,
            currency=currency,
        )
    
    async def verify_webhook(self, out_sum: str, inv_id: str, signature: str) -> bool:
        """Verify webhook signature (backward compatibility).
        
        Delegates to RobokassaWebhookHandler.verify_webhook.
        """
        return await self._webhook_handler.verify_webhook(
            out_sum=out_sum,
            inv_id=inv_id,
            signature=signature,
        )
    
    async def process_webhook(
        self, out_sum: str, inv_id: str, signature: str, shp_params: dict
    ):
        """Process webhook (backward compatibility).
        
        Delegates to RobokassaWebhookHandler.process_webhook.
        """
        return await self._webhook_handler.process_webhook(
            out_sum=out_sum,
            inv_id=inv_id,
            signature=signature,
            shp_params=shp_params,
        )
