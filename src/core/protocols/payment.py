"""Protocol for payment service."""

from typing import Optional, Protocol


class PaymentServiceProtocol(Protocol):
    """Protocol for payment service implementations.
    
    This protocol allows easy mocking and testing of code that creates payments.
    Re-exports from payment.interfaces for consistency.
    """
    
    async def create_payment(
        self,
        amount: int,  # in smallest currency unit (kopecks/cents)
        pair_id: int,
        return_url: str,
        period_days: int = 30,
        is_lifetime: bool = False,
        currency: str = "RUB",
    ) -> Optional[dict]:
        """Create payment link.
        
        Args:
            amount: Payment amount in smallest currency unit
            pair_id: Pair ID for subscription
            return_url: URL to redirect user after payment
            period_days: Subscription period in days (ignored if is_lifetime=True)
            is_lifetime: Whether this is a lifetime subscription
            currency: Currency code (e.g., "RUB", "USD")
            
        Returns:
            Payment data dict with at least:
            - "id": Payment ID
            - "confirmation": {"confirmation_url": str}
            - "metadata": dict with pair_id, period_days, is_lifetime
            None if payment creation failed
        """
        ...
    
    async def verify_webhook(self, *args, **kwargs) -> bool:
        """Verify webhook signature.
        
        Args:
            *args, **kwargs: Provider-specific webhook parameters
            
        Returns:
            True if signature is valid, False otherwise
        """
        ...
    
    async def process_webhook(self, *args, **kwargs) -> Optional[dict]:
        """Process webhook notification.
        
        Args:
            *args, **kwargs: Provider-specific webhook parameters
            
        Returns:
            Processed payment data dict with at least:
            - "payment_id": str
            - "pair_id": int
            - "amount": str
            - "currency": str
            - "period_days": int | None
            - "is_lifetime": bool
            - "status": str
            None if webhook processing failed
        """
        ...

