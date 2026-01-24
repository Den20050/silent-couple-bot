"""Webhook handler for Robokassa ResultURL."""

from typing import Optional

try:
    from redis.asyncio import Redis
except ImportError:  # pragma: no cover
    # Optional dependency in some tooling environments (e.g., linters).
    Redis = object  # type: ignore[assignment]

from src.core.config import Settings
from src.core.logger import get_logger
from src.services.payment.robokassa_service import RobokassaService

logger = get_logger(__name__)


class RobokassaWebhookHandler:
    """Handler for Robokassa ResultURL webhook notifications."""

    def __init__(self, redis: Redis | None, settings: Settings) -> None:
        """Initialize webhook handler.

        Args:
            redis: Redis client for circuit breaker (optional)
            settings: Application settings
        """
        self.service = RobokassaService(redis=redis, settings=settings)

    async def verify_webhook(
        self,
        out_sum: str,
        inv_id: str,
        signature: str,
        shp_params: dict[str, str] | None = None,
    ) -> bool:
        """Verify Robokassa ResultURL webhook signature.

        Args:
            out_sum: Payment amount as string
            inv_id: Invoice ID
            signature: Signature from webhook

        Returns:
            True if signature is valid, False otherwise
        """
        return await self.service.verify_webhook(
            out_sum=out_sum,
            inv_id=inv_id,
            signature=signature,
            shp_params=shp_params,
        )

    async def process_webhook(
        self, out_sum: str, inv_id: str, signature: str, shp_params: dict
    ) -> Optional[dict]:
        """Process Robokassa ResultURL webhook.

        Args:
            out_sum: Payment amount as string
            inv_id: Invoice ID
            signature: Signature from webhook
            shp_params: Dictionary of Shp_ parameters from query string

        Returns:
            Processed payment data dict with:
            - "payment_id": Invoice ID (inv_id)
            - "pair_id": int
            - "amount": str
            - "currency": str
            - "period_days": int | None
            - "is_lifetime": bool
            - "status": "succeeded"
            None if webhook processing failed
        """
        # Verify signature
        if not await self.verify_webhook(
            out_sum,
            inv_id,
            signature,
            shp_params=shp_params,
        ):
            logger.warning(
                "Invalid Robokassa webhook signature",
                inv_id=inv_id,
                out_sum=out_sum,
            )
            return None

        # Extract parameters from shp_ (Shp parameters)
        pair_id = int(shp_params.get("pair_id", 0))
        is_lifetime = shp_params.get("is_lifetime", "false").lower() == "true"
        currency = shp_params.get("currency", "RUB")  # Payment currency

        if is_lifetime:
            period_days = None
        else:
            period_days_str = shp_params.get("period_days", "30")
            try:
                period_days = int(period_days_str)
            except (ValueError, TypeError):
                period_days = 30  # Default fallback

        logger.info(
            "Robokassa payment succeeded",
            inv_id=inv_id,
            pair_id=pair_id,
            out_sum=out_sum,
            currency=currency,
            period_days=period_days,
            is_lifetime=is_lifetime,
        )

        return {
            "payment_id": inv_id,  # Use inv_id as payment_id
            "pair_id": pair_id,
            "amount": out_sum,
            "currency": currency,
            "period_days": int(period_days) if period_days else None,
            "is_lifetime": is_lifetime,
            "status": "succeeded",
        }
