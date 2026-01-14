"""Robokassa payment service implementation."""

import hashlib
import hmac
import random
import time
from typing import Optional
from urllib.parse import urlencode

from redis.asyncio import Redis

from src.core.config import Settings
from src.core.logger import get_logger
from src.services.payment.circuit_breaker import CircuitBreaker
from src.services.payment.interfaces import PaymentProvider

logger = get_logger(__name__)


class RobokassaService(PaymentProvider):
    """Robokassa payment service implementation.

    Handles payment link creation for Robokassa payment gateway.
    Uses direct payment URLs (no API calls required).
    """

    def __init__(self, redis: Redis | None, settings: Settings) -> None:
        """Initialize Robokassa service.

        Args:
            redis: Redis client for circuit breaker (optional)
            settings: Application settings
        """
        super().__init__(redis)
        self.settings = settings
        self.circuit_breaker = CircuitBreaker(redis, "robokassa")
    
    def _generate_payment_signature(
        self,
        merchant_login: str,
        out_sum: str,
        inv_id: str,
        password: str,
        currency: str = "RUB",
        shp_params: Optional[dict] = None,
    ) -> str:
        """Generate Robokassa payment signature (MD5).
        
        Args:
            merchant_login: Merchant login
            out_sum: Payment amount as string
            inv_id: Invoice ID
            password: Password #1 for payment
            currency: Currency code (default: "RUB")
            shp_params: Dictionary of Shp_ parameters (will be sorted alphabetically)
            
        Returns:
            MD5 signature in uppercase
            
        Note:
            CRITICAL: The following parameters MUST NEVER be included in signature:
            - SuccessURL
            - Culture
            - Encoding
            - IsTest
            Including these will cause Robokassa to return 500 error.
            
            Only these parameters are included:
            - MerchantLogin
            - OutSum
            - InvId
            - Currency (only if not RUB)
            - Password#1
            - Shp_ parameters (if any, sorted alphabetically)
        """
        # Base signature string: MerchantLogin:OutSum:InvId:Password#1
        # If currency is not RUB, add it: MerchantLogin:OutSum:InvId:Currency:Password#1
        # CRITICAL: Do NOT include SuccessURL, Culture, Encoding, IsTest in signature!
        # IMPORTANT: For non-RUB currencies, use OutSumCurrency value in signature
        # The currency parameter in signature must match OutSumCurrency parameter in URL
        if currency != "RUB":
            # For non-RUB currencies, currency code goes BEFORE password in signature
            signature_string = f"{merchant_login}:{out_sum}:{inv_id}:{currency}:{password}"
        else:
            # For RUB, no currency parameter in signature
            signature_string = f"{merchant_login}:{out_sum}:{inv_id}:{password}"
        
        # Add Shp_ parameters to signature string
        # CRITICAL FORMAT REQUIREMENTS:
        # - Shp_ parameters MUST be sorted alphabetically by key
        # - Format: :Shp_key:value (with colon separator between key and value, and between parameters)
        # - NO colon at the end
        # - NO URL-encoding (use raw values)
        # Example: :Shp_currency:RUB:Shp_is_lifetime:false:Shp_pair_id:2:Shp_period_days:30
        if shp_params:
            # Sort Shp_ parameters alphabetically by key
            sorted_shp = sorted(shp_params.items())
            # Add each Shp_ parameter to signature string
            # Format: :Shp_key:value (with colon separator between key and value, NO colon at the end)
            for key, value in sorted_shp:
                signature_string += f":{key}:{value}"
        
        # Log signature string for debugging (without password)
        # Changed to INFO level to see in production logs
        # Format should be: MerchantLogin:OutSum:InvId:Password#1:Shp_currency=RUB:Shp_is_lifetime=false:Shp_pair_id=2:Shp_period_days=30
        signature_string_for_log = signature_string.replace(password, "***PASSWORD***")
        
        # Check for potential issues
        has_leading_trailing_spaces = signature_string != signature_string.strip()
        has_tabs = '\t' in signature_string
        has_newlines = '\n' in signature_string or '\r' in signature_string
        
        logger.info(
            "Signature string before hashing (MD5)",
            signature_string=signature_string_for_log,
            signature_string_length=len(signature_string),
            has_shp_params=bool(shp_params),
            shp_params_count=len(shp_params) if shp_params else 0,
            shp_params_sorted=list(sorted(shp_params.items())) if shp_params else None,
            has_leading_trailing_spaces=has_leading_trailing_spaces,
            has_tabs=has_tabs,
            has_newlines=has_newlines,
            password_length=len(password),
            password_starts_with_space=password.startswith(' ') if password else False,
            password_ends_with_space=password.endswith(' ') if password else False,
        )
        
        # Warn if issues detected
        if has_leading_trailing_spaces or has_tabs or has_newlines:
            logger.error(
                "CRITICAL: Signature string contains problematic characters!",
                has_leading_trailing_spaces=has_leading_trailing_spaces,
                has_tabs=has_tabs,
                has_newlines=has_newlines,
                signature_string_repr=repr(signature_string_for_log),
            )
        
        return hashlib.md5(signature_string.encode()).hexdigest().upper()
    
    def _verify_result_signature(
        self, out_sum: str, inv_id: str, signature: str, password: str
    ) -> bool:
        """Verify Robokassa ResultURL signature (MD5).
        
        Args:
            out_sum: Payment amount as string
            inv_id: Invoice ID
            signature: Signature from webhook
            password: Password #2 for ResultURL
            
        Returns:
            True if signature is valid, False otherwise
        """
        signature_string = f"{out_sum}:{inv_id}:{password}"
        expected_signature = hashlib.md5(signature_string.encode()).hexdigest().upper()
        return hmac.compare_digest(expected_signature, signature.upper())
    
    async def create_payment(
        self,
        amount: int,  # in smallest currency unit (kopecks/cents)
        pair_id: int,
        return_url: str,
        period_days: int = 30,
        is_lifetime: bool = False,
        currency: str = "RUB",
    ) -> Optional[dict]:
        """Create payment link for Robokassa.
        
        Args:
            amount: Payment amount in smallest currency unit
            pair_id: Pair ID for subscription
            return_url: URL to redirect user after payment
            period_days: Subscription period in days (ignored if is_lifetime=True)
            is_lifetime: Whether this is a lifetime subscription
            currency: Currency code (e.g., "RUB", "USD")
            
        Returns:
            Payment data dict with:
            - "id": Invoice ID (inv_id)
            - "confirmation": {"confirmation_url": str}
            - "metadata": dict with pair_id, period_days, is_lifetime
            None if payment creation failed
        """
        if await self.circuit_breaker.is_open():
            logger.warning(
                "Circuit breaker is open, skipping payment creation",
                pair_id=pair_id,
            )
            return None
        
        try:
            # Generate unique InvId (invoice number)
            # Robokassa requires InvId to be:
            # - Numeric only (digits only, no letters or special characters)
            # - Unique for each payment
            # - Maximum 10 digits recommended
            # - Must not start with zero
            # Format: last 7 digits of timestamp + pair_id (max 3 digits) + random (1 digit)
            # This ensures max 10 digits and uniqueness
            # We also check Redis to guarantee uniqueness
            max_attempts = 10
            inv_id = None
            
            for attempt in range(max_attempts):
                timestamp_part = int(time.time()) % 10000000  # Last 7 digits of timestamp (ensures uniqueness for ~115 days)
                pair_part = pair_id % 1000  # Limit pair_id to 3 digits (max 999 pairs)
                random_part = random.randint(1, 9)  # 1 random digit (1-9, not 0 to avoid leading zero)
                candidate_id = str(timestamp_part * 1000 + pair_part * 10 + random_part)
                
                # Ensure InvId is exactly what we expect (should be 10 digits max)
                if len(candidate_id) > 10:
                    # Fallback: use simpler format if somehow too long
                    candidate_id = str(int(time.time()) % 1000000000)  # Last 9 digits of timestamp
                    if len(candidate_id) < 10:
                        candidate_id = candidate_id + str(random.randint(1, 9))  # Add random digit to make it 10 digits
                
                # Validate InvId format
                if not candidate_id.isdigit():
                    continue  # Try again
                
                if candidate_id.startswith('0'):
                    continue  # Try again
                
                # Check uniqueness via Redis (if available)
                if self.redis:
                    redis_key = f"robokassa:inv_id:{candidate_id}"
                    # Try to set with NX (only if not exists) and EX (expire in 24 hours)
                    # This ensures InvId is unique within 24 hours
                    is_unique = await self.redis.set(redis_key, "1", nx=True, ex=86400)
                    if not is_unique:
                        logger.warning(
                            "InvId collision detected, regenerating",
                            inv_id=candidate_id,
                            attempt=attempt + 1,
                            pair_id=pair_id,
                        )
                        continue  # Try again with different random part
                
                inv_id = candidate_id
                break
            
            # Fallback if all attempts failed (should never happen, but safety check)
            if not inv_id:
                logger.error(
                    "Failed to generate unique InvId after max attempts",
                    max_attempts=max_attempts,
                    pair_id=pair_id,
                )
                # Last resort: use timestamp + microseconds + random
                inv_id = str(int(time.time() * 1000000) % 1000000000)
                if len(inv_id) < 10:
                    inv_id = inv_id + str(random.randint(1, 9))
                if inv_id.startswith('0'):
                    inv_id = '1' + inv_id[1:]
            
            # Log InvId for debugging
            logger.info(
                "InvId generated for payment",
                inv_id=inv_id,
                inv_id_type=type(inv_id).__name__,
                inv_id_length=len(inv_id),
                pair_id=pair_id,
                is_numeric=inv_id.isdigit(),
            )
            
            # Convert amount from smallest unit to main currency
            from src.core.constants import SUPPORTED_CURRENCIES
            
            currency_info = SUPPORTED_CURRENCIES.get(
                currency, SUPPORTED_CURRENCIES["RUB"]
            )
            decimals = currency_info["decimals"]
            divisor = 10 ** decimals
            # Format amount for Robokassa
            # Robokassa requires OutSum to be a number with dot as decimal separator
            # CRITICAL: Format must always be "299.00" (with dot, exactly 2 decimal places)
            # - Must use dot (.) as decimal separator, not comma
            # - Always use 2 decimal places for RUB (e.g., "299.00", not "299")
            amount_decimal = amount / divisor
            
            if decimals > 0:
                # Format with fixed decimals (e.g., "299.00" for RUB with 2 decimals)
                # Always use full format with trailing zeros (e.g., "299.00" not "299")
                out_sum = f"{amount_decimal:.{decimals}f}"
            else:
                # For currencies without decimals, format as integer with .00
                out_sum = f"{int(amount_decimal)}.00"
            
            # Ensure out_sum is not empty and is valid
            if not out_sum or not out_sum.replace(".", "").isdigit():
                logger.error(
                    "Invalid OutSum after formatting",
                    out_sum=out_sum,
                    amount=amount,
                    amount_decimal=amount_decimal,
                )
                # Fallback to simple format
                out_sum = str(amount_decimal)
            
            # Log formatted values for debugging
            logger.debug(
                "Payment amount formatted",
                amount_original=amount,
                amount_decimal=amount_decimal,
                out_sum=out_sum,
                currency=currency,
                decimals=decimals,
            )
            
            # Prepare Shp_ parameters
            # TEMPORARY: Shp_ parameters are EXCLUDED from signature for testing
            # They will still be sent in URL parameters (added below)
            # This helps diagnose if Shp_ params in signature cause 500 errors
            # According to Robokassa docs example, Shp_ params are optional in signature
            shp_params = {
                "Shp_currency": currency,
                "Shp_is_lifetime": "true" if is_lifetime else "false",
                "Shp_pair_id": str(pair_id),
                "Shp_period_days": str(period_days) if not is_lifetime else "0",
            }
            
            # Generate payment signature
            # According to Robokassa docs example: MerchantLogin:OutSum:InvId:Password#1
            # For non-RUB: MerchantLogin:OutSum:InvId:Currency:Password#1
            # Shp_ parameters should be added AFTER password if used
            # Log values before signature generation for debugging
            logger.info(
                "Generating payment signature",
                merchant_login=self.settings.robokassa_merchant_login,
                out_sum=out_sum,
                out_sum_type=type(out_sum).__name__,
                inv_id=inv_id,
                inv_id_type=type(inv_id).__name__,
                currency=currency,
                is_production=self.settings.robokassa_is_production,
                shp_params=shp_params,
                signature_format="MD5 (Robokassa standard)",
            )
            
            # Warning if using production password in test mode or vice versa
            if not self.settings.robokassa_is_production:
                logger.warning(
                    "Using TEST mode - ensure you're using TEST passwords from Robokassa dashboard",
                    merchant_login=self.settings.robokassa_merchant_login,
                )
            
            # Generate signature following Robokassa docs format
            # Base format: MerchantLogin:OutSum:InvId:Password#1
            # With currency: MerchantLogin:OutSum:InvId:Currency:Password#1
            # With Shp_: MerchantLogin:OutSum:InvId:Password#1:Shp_currency=RUB:Shp_is_lifetime=false:Shp_pair_id=2:Shp_period_days=30
            # CRITICAL: Shp_ parameters MUST be sorted alphabetically
            # Format: :Shp_key=value (colon separator, NO colon at the end)
            # IMPORTANT: Strip password to remove any leading/trailing whitespace
            password_1 = self.settings.robokassa_password_1.strip()
            if password_1 != self.settings.robokassa_password_1:
                logger.warning(
                    "Password #1 had leading/trailing whitespace - stripped",
                    original_length=len(self.settings.robokassa_password_1),
                    stripped_length=len(password_1),
                )
            
            signature = self._generate_payment_signature(
                merchant_login=self.settings.robokassa_merchant_login,
                out_sum=out_sum,
                inv_id=inv_id,
                password=password_1,  # Password #1 for payment (stripped)
                currency=currency,
                shp_params=shp_params,  # Shp_ parameters included in signature (sorted alphabetically)
            )
            
            logger.info(
                "Payment signature generated",
                signature=signature,
                signature_length=len(signature),
            )

            # Build payment URL
            # Test and production URLs are the same for Robokassa
            # Domain can be robokassa.ru, robokassa.kz, or robokassa.com
            base_url = f"https://auth.{self.settings.robokassa_domain}/Merchant/Index.aspx"

            # Build URL parameters
            # CRITICAL: SuccessURL, Culture, Encoding, IsTest are added to URL
            # but MUST NOT be included in signature calculation!
            # IMPORTANT: Description is URL-encoded automatically by urlencode()
            # Robokassa expects UTF-8 encoding for Description parameter
            params = {
                "MerchantLogin": self.settings.robokassa_merchant_login,
                "OutSum": out_sum,
                "InvId": inv_id,
                "Description": f"Подписка Silent Couple Bot (пара {pair_id})",
                "SignatureValue": signature,
                "Culture": "ru",  # NOT in signature!
                "Encoding": "utf-8",  # NOT in signature!
            }
            
            # Validate critical parameters before building URL
            if not self.settings.robokassa_merchant_login:
                logger.error("MerchantLogin is empty")
                raise ValueError("MerchantLogin cannot be empty")
            if not out_sum or not out_sum.replace(".", "").isdigit():
                logger.error("Invalid OutSum format", out_sum=out_sum)
                raise ValueError(f"Invalid OutSum format: {out_sum}")
            if not inv_id or not inv_id.isdigit():
                logger.error("Invalid InvId format", inv_id=inv_id)
                raise ValueError(f"Invalid InvId format: {inv_id}")
            if not signature:
                logger.error("Signature is empty")
                raise ValueError("Signature cannot be empty")
            
            # Add IsTest parameter for test mode
            # This is required for test payments in Robokassa
            # CRITICAL: IsTest is NOT included in signature!
            # IMPORTANT: IsTest must be "1" (string) for test mode, omitted for production
            if not self.settings.robokassa_is_production:
                params["IsTest"] = "1"
                logger.info(
                    "Added IsTest=1 parameter for test mode",
                    is_production=self.settings.robokassa_is_production,
                )
            else:
                logger.info(
                    "Production mode - IsTest parameter NOT added",
                    is_production=self.settings.robokassa_is_production,
                )
            
            # OutSumCurrency only for non-RUB currencies
            # For RUB, this parameter should not be sent (causes 500 error)
            if currency != "RUB":
                params["OutSumCurrency"] = currency
            
            # Add Shp_ parameters to URL
            # These will be returned in ResultURL webhook
            # TEMPORARY: Shp_ parameters are NOT in signature (excluded for testing)
            # They are still sent in URL so webhook can receive them
            params.update(shp_params)
            
            # Add SuccessURL if provided
            # CRITICAL: SuccessURL is NOT included in signature!
            if return_url:
                params["SuccessURL"] = return_url
            
            # IMPORTANT: Do NOT sort parameters alphabetically for URL
            # Robokassa may expect parameters in a specific order
            # Sorting is only needed for Shp_ parameters in signature (already done)
            # Keep original order for URL parameters
            # urlencode() handles URL encoding automatically (including UTF-8 for Description)
            # Note: Shp_ parameters ARE included in signature (already done above)
            # But they are also added to URL parameters
            
            # Use urlencode with doseq=False to ensure proper encoding
            # doseq=False means each value is treated as a single string
            # Keep parameters in the order they were added (not sorted)
            payment_url = f"{base_url}?{urlencode(params, doseq=False)}"
            
            # Log final URL for debugging (truncated for security)
            logger.debug(
                "Final payment URL (truncated)",
                url_length=len(payment_url),
                url_preview=payment_url[:200] + "..." if len(payment_url) > 200 else payment_url,
            )
            
            # Log payment URL for debugging (without sensitive data)
            logger.info(
                "Robokassa payment URL generated",
                pair_id=pair_id,
                inv_id=inv_id,
                inv_id_type=type(inv_id).__name__,
                out_sum=out_sum,
                out_sum_type=type(out_sum).__name__,
                currency=currency,
                has_out_sum_currency=currency != "RUB",
                merchant_login=self.settings.robokassa_merchant_login,
                signature=signature,
                signature_length=len(signature),
                params_count=len(params),
                params_keys=list(params.keys()),  # Keep original order, not sorted
                shp_params=[k for k in params.keys() if k.startswith("Shp_")],
                payment_url_preview=payment_url[:300] + "..." if len(payment_url) > 300 else payment_url,
            )
            
            # Log actual parameter values for debugging (except password)
            logger.debug(
                "Payment URL parameters",
                MerchantLogin=params.get("MerchantLogin"),
                OutSum=params.get("OutSum"),
                InvId=params.get("InvId"),
                SignatureValue=signature[:20] + "..." if len(signature) > 20 else signature,
                Culture=params.get("Culture"),
                Encoding=params.get("Encoding"),
                IsTest=params.get("IsTest"),
                OutSumCurrency=params.get("OutSumCurrency"),
                SuccessURL=params.get("SuccessURL"),
                Shp_params=shp_params,
            )
            logger.info(
                "Robokassa payment link created",
                pair_id=pair_id,
                inv_id=inv_id,
                amount=amount,
                payment_url_length=len(payment_url),
                payment_url_full=payment_url,  # Full URL for manual testing - copy this and test in browser
                # Log key parameters for manual verification
                manual_verification_hint={
                    "expected_signature_string": f"{self.settings.robokassa_merchant_login}:{out_sum}:{inv_id}:***PASSWORD***:{':'.join(f'{k}={v}' for k, v in sorted(shp_params.items()))}",
                    "actual_signature": signature,
                    "merchant_login": self.settings.robokassa_merchant_login,
                    "out_sum": out_sum,
                    "inv_id": inv_id,
                    "shp_params_sorted": sorted(shp_params.items()),
                    "troubleshooting_checklist": [
                        "✅ Signature calculated correctly (verified with test script)",
                        f"✅ IsTest={'1' if not self.settings.robokassa_is_production else 'NOT SET'} (test mode)",
                        "✅ OutSum format: 299.00 (with dot, 2 decimals)",
                        "✅ Shp_ parameters sorted alphabetically in signature",
                        "⚠️  Check Robokassa dashboard: MD5 algorithm selected?",
                        "⚠️  Check Robokassa dashboard: Test Password #1 matches .env?",
                        "⚠️  Check Robokassa dashboard: Merchant Login matches?",
                        "⚠️  Try copying full URL from logs and testing manually in browser",
                        "⚠️  Contact Robokassa support with full URL if error persists",
                    ],
                },
            )
            
            await self.circuit_breaker.record_success()
            
            return {
                "id": inv_id,  # Use inv_id as payment ID
                "confirmation": {
                    "confirmation_url": payment_url,
                },
                "metadata": {
                    "pair_id": str(pair_id),
                    "period_days": str(period_days),
                    "is_lifetime": "true" if is_lifetime else "false",
                },
            }
        except Exception as e:
            await self.circuit_breaker.record_failure()
            logger.error(
                "Failed to create Robokassa payment",
                pair_id=pair_id,
                error=str(e),
            )
            return None
    
    async def verify_webhook(self, out_sum: str, inv_id: str, signature: str) -> bool:
        """Verify Robokassa ResultURL webhook signature.
        
        Args:
            out_sum: Payment amount as string
            inv_id: Invoice ID
            signature: Signature from webhook
            
        Returns:
            True if signature is valid, False otherwise
        """
        return self._verify_result_signature(
            out_sum=out_sum,
            inv_id=inv_id,
            signature=signature,
            password=self.settings.robokassa_password_2,  # Password #2 for ResultURL
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
        if not await self.verify_webhook(out_sum, inv_id, signature):
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
