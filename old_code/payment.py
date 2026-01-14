"""Payment service with circuit breaker."""

import hashlib
import hmac
import random
import time
from typing import Optional
from urllib.parse import urlencode

from redis.asyncio import Redis

from src.core.config import settings
from src.core.constants import (  # noqa: E501
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_TIMEOUT_SECONDS,
)
from src.core.logger import get_logger

logger = get_logger(__name__)


class CircuitBreaker:
    """Circuit breaker for external services."""

    def __init__(self, redis: Redis | None, service_name: str):
        """Initialize circuit breaker."""
        self.redis = redis
        self.service_name = service_name
        self.key_prefix = f"cb:{service_name}"
        self._redis_available = redis is not None

    async def is_open(self) -> bool:
        """Check if circuit is open."""
        if not self._redis_available or not self.redis:
            return False  # If Redis unavailable, circuit breaker is always closed (allows requests)
        
        try:
            key = f"{self.key_prefix}:open"
            # Use get with timeout to avoid hanging
            result = await self.redis.get(key)
            return result is not None
        except (ConnectionError, Exception) as e:
            # Catch all Redis connection errors
            logger.warning(
                "Circuit breaker Redis error, treating as closed",
                service=self.service_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            self._redis_available = False  # Disable Redis for future calls
            self.redis = None  # Clear reference to failed Redis client
            return False  # Allow request if Redis fails

    async def record_failure(self) -> None:
        """Record a failure."""
        if not self._redis_available or not self.redis:
            return  # Skip if Redis unavailable
        
        try:
            key = f"{self.key_prefix}:failures"
            count = await self.redis.incr(key)
            await self.redis.expire(key, CIRCUIT_BREAKER_TIMEOUT_SECONDS)
            
            if count >= CIRCUIT_BREAKER_FAILURE_THRESHOLD:
                await self._open_circuit()
        except Exception as e:
            logger.warning(
                "Circuit breaker Redis error in record_failure",
                service=self.service_name,
                error=str(e),
            )
            self._redis_available = False  # Disable Redis for future calls

    async def _open_circuit(self) -> None:
        """Open circuit breaker."""
        if not self._redis_available or not self.redis:
            return
        
        try:
            key = f"{self.key_prefix}:open"
            await self.redis.setex(key, CIRCUIT_BREAKER_TIMEOUT_SECONDS, "1")
            logger.error(
                "Circuit breaker opened",
                service=self.service_name,
                timeout=CIRCUIT_BREAKER_TIMEOUT_SECONDS,
            )
        except Exception as e:
            logger.warning(
                "Circuit breaker Redis error in _open_circuit",
                service=self.service_name,
                error=str(e),
            )
            self._redis_available = False

    async def record_success(self) -> None:
        """Record a success (reset failures)."""
        if not self._redis_available or not self.redis:
            return
        
        try:
            key = f"{self.key_prefix}:failures"
            await self.redis.delete(key)
        except Exception as e:
            logger.warning(
                "Circuit breaker Redis error in record_success",
                service=self.service_name,
                error=str(e),
            )
            self._redis_available = False


# =============================================================================
# YooKassa Payment Service (DEPRECATED - закомментировано)
# =============================================================================
# class PaymentService:
#     """YooKassa payment service."""
#
#     def __init__(self, redis: Redis | None):
#         """Initialize payment service."""
#         self.redis = redis
#         self.circuit_breaker = CircuitBreaker(redis, "yookassa")
#         self.base_url = "https://api.yookassa.ru/v3"


class PaymentService:
    """Robokassa payment service."""

    def __init__(self, redis: Redis | None):
        """Initialize payment service."""
        self.redis = redis
        self.circuit_breaker = CircuitBreaker(redis, "robokassa")
        # Робокасса использует прямые ссылки на оплату, не требует API URL

    # =============================================================================
    # YooKassa methods (DEPRECATED - закомментировано)
    # =============================================================================
    # def _generate_idempotency_key(self, pair_id: int, amount: int) -> str:
    #     """Generate idempotency key."""
    #     data = f"{pair_id}:{amount}:{date.today().isoformat()}"
    #     return hashlib.sha256(data.encode()).hexdigest()
    #
    # def _verify_webhook_signature(self, body: str, signature: str) -> bool:
    #     """Verify YooKassa webhook signature."""
    #     expected_signature = hmac.new(
    #         settings.yookassa_secret_key.encode(),
    #         body.encode(),
    #         hashlib.sha256,
    #     ).hexdigest()
    #     return hmac.compare_digest(expected_signature, signature)

    def _generate_payment_signature(
        self,
        merchant_login: str,
        out_sum: str,
        inv_id: str,
        password: str,
        currency: str = "RUB",
    ) -> str:
        """Generate Robokassa payment signature (MD5)."""
        # Если валюта не RUB, добавляем её в подпись
        if currency != "RUB":
            signature_string = f"{merchant_login}:{out_sum}:{inv_id}:{currency}:{password}"
        else:
            signature_string = f"{merchant_login}:{out_sum}:{inv_id}:{password}"
        return hashlib.md5(signature_string.encode()).hexdigest().upper()

    def _verify_result_signature(
        self, out_sum: str, inv_id: str, signature: str, password: str
    ) -> bool:
        """Verify Robokassa ResultURL signature (MD5)."""
        signature_string = f"{out_sum}:{inv_id}:{password}"
        expected_signature = hashlib.md5(signature_string.encode()).hexdigest().upper()
        return hmac.compare_digest(expected_signature, signature.upper())

    # =============================================================================
    # YooKassa create_payment (DEPRECATED - закомментировано)
    # =============================================================================
    # async def create_payment(
    #     self,
    #     amount: int,  # in kopecks
    #     pair_id: int,
    #     return_url: str,
    #     period_days: int = 30,  # Subscription period in days
    #     is_lifetime: bool = False,  # Lifetime subscription flag
    # ) -> Optional[dict]:
    #     """Create payment in YooKassa."""
    #     if await self.circuit_breaker.is_open():
    #         logger.warning(
    #             "Circuit breaker is open, skipping payment creation",
    #             pair_id=pair_id,
    #         )
    #         return None
    #
    #     idempotency_key = self._generate_idempotency_key(pair_id, amount)
    #     
    #     payload = {
    #         "amount": {
    #             "value": f"{amount / 100:.2f}",
    #             "currency": "RUB",
    #         },
    #         "confirmation": {
    #             "type": "redirect",
    #             "return_url": return_url,
    #         },
    #         "description": f"Подписка Silent Couple Bot (пара {pair_id})",
    #         "metadata": {
    #             "pair_id": str(pair_id),
    #             "period_days": str(period_days),
    #             "is_lifetime": "true" if is_lifetime else "false",
    #         },
    #     }
    #
    #     headers = {
    #         "Idempotence-Key": idempotency_key,
    #         "Content-Type": "application/json",
    #     }
    #
    #     auth = (settings.yookassa_shop_id, settings.yookassa_secret_key)
    #
    #     try:
    #         async with httpx.AsyncClient() as client:
    #             response = await client.post(
    #                 f"{self.base_url}/payments",
    #                 json=payload,
    #                 headers=headers,
    #                 auth=auth,
    #                 timeout=10.0,
    #             )
    #             response.raise_for_status()
    #             result = response.json()
    #             
    #             await self.circuit_breaker.record_success()
    #             logger.info(
    #                 "Payment created",
    #                 pair_id=pair_id,
    #                 payment_id=result.get("id"),
    #             )
    #             return result
    #     except Exception as e:
    #         await self.circuit_breaker.record_failure()
    #         logger.error(
    #             "Failed to create payment",
    #             pair_id=pair_id,
    #             error=str(e),
    #         )
    #         return None

    async def create_payment(
        self,
        amount: int,  # in smallest currency unit (kopecks/cents)
        pair_id: int,
        return_url: str,
        period_days: int = 30,  # Subscription period in days
        is_lifetime: bool = False,  # Lifetime subscription flag
        currency: str = "RUB",  # Currency code
    ) -> Optional[dict]:
        """Create payment link for Robokassa."""
        if await self.circuit_breaker.is_open():
            logger.warning(
                "Circuit breaker is open, skipping payment creation",
                pair_id=pair_id,
            )
            return None

        try:
            # Генерируем уникальный InvId (номер счета)
            # Используем комбинацию pair_id, timestamp и random для уникальности
            inv_id = f"{pair_id}_{int(time.time())}_{random.randint(1000, 9999)}"
            
            # Конвертируем сумму из smallest unit в основную валюту
            from src.core.constants import SUPPORTED_CURRENCIES

            currency_info = SUPPORTED_CURRENCIES.get(
                currency, SUPPORTED_CURRENCIES["RUB"]
            )
            decimals = currency_info["decimals"]
            divisor = 10 ** decimals
            out_sum = f"{amount / divisor:.{decimals}f}"
            
            # Генерируем подпись для оплаты
            signature = self._generate_payment_signature(
                merchant_login=settings.robokassa_merchant_login,
                out_sum=out_sum,
                inv_id=inv_id,
                password=settings.robokassa_password_1,  # Password #1 для оплаты
                currency=currency,
            )
            
            # Формируем URL для оплаты
            # Тестовый или продакшн URL определяется через настройки
            base_url = (
                "https://auth.robokassa.ru/Merchant/Index.aspx"
                if settings.robokassa_is_production
                else "https://auth.robokassa.ru/Merchant/Index.aspx"  # Тестовый URL тот же
            )
            
            # Формируем параметры для URL
            params = {
                "MerchantLogin": settings.robokassa_merchant_login,
                "OutSum": out_sum,
                "InvId": inv_id,
                "Description": f"Подписка Silent Couple Bot (пара {pair_id})",
                "SignatureValue": signature,
                "Culture": "ru",
                "Encoding": "utf-8",
                # Валюта для Робокассы
                "OutSumCurrency": currency,
                # Передаем дополнительные параметры через Shp_ префикс
                "Shp_pair_id": str(pair_id),
                "Shp_period_days": str(period_days) if not is_lifetime else "0",
                "Shp_is_lifetime": "true" if is_lifetime else "false",
                "Shp_currency": currency,
            }
            
            # Если указан SuccessURL, добавляем его
            if return_url:
                params["SuccessURL"] = return_url
            
            payment_url = f"{base_url}?{urlencode(params)}"
            
            await self.circuit_breaker.record_success()
            logger.info(
                "Robokassa payment link created",
                pair_id=pair_id,
                inv_id=inv_id,
                amount=amount,
            )
            
            return {
                "id": inv_id,  # Используем inv_id как ID платежа
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

    # =============================================================================
    # YooKassa webhook methods (DEPRECATED - закомментировано)
    # =============================================================================
    # async def verify_webhook(self, body: str, signature: str) -> bool:
    #     """Verify webhook signature."""
    #     return self._verify_webhook_signature(body, signature)
    #
    # async def process_webhook(self, webhook_data: dict) -> Optional[dict]:
    #     """Process YooKassa webhook."""
    #     event = webhook_data.get("event")
    #     payment = webhook_data.get("object", {})
    #     
    #     if event == "payment.succeeded":
    #         payment_id = payment.get("id")
    #         metadata = payment.get("metadata", {})
    #         pair_id = int(metadata.get("pair_id", 0))
    #         is_lifetime = metadata.get("is_lifetime", "false").lower() == "true"
    #         period_days = None if is_lifetime else int(metadata.get("period_days", 30))  # None for lifetime
    #         
    #         logger.info(
    #             "Payment succeeded",
    #             payment_id=payment_id,
    #             pair_id=pair_id,
    #             period_days=period_days,
    #             is_lifetime=is_lifetime,
    #         )
    #         
    #         return {
    #             "payment_id": payment_id,
    #             "pair_id": pair_id,
    #             "amount": payment.get("amount", {}).get("value"),
    #             "period_days": period_days,
    #             "is_lifetime": is_lifetime,
    #             "status": "succeeded",
    #         }
    #     
    #     return None

    async def verify_webhook(self, out_sum: str, inv_id: str, signature: str) -> bool:
        """Verify Robokassa ResultURL webhook signature."""
        return self._verify_result_signature(
            out_sum=out_sum,
            inv_id=inv_id,
            signature=signature,
            password=settings.robokassa_password_2,  # Password #2 для ResultURL
        )

    async def process_webhook(
        self, out_sum: str, inv_id: str, signature: str, shp_params: dict
    ) -> Optional[dict]:
        """Process Robokassa ResultURL webhook."""
        # Проверяем подпись
        if not await self.verify_webhook(out_sum, inv_id, signature):
            logger.warning(
                "Invalid Robokassa webhook signature",
                inv_id=inv_id,
                out_sum=out_sum,
            )
            return None
        
        # Извлекаем параметры из shp_ (Shp параметры)
        pair_id = int(shp_params.get("pair_id", 0))
        is_lifetime = shp_params.get("is_lifetime", "false").lower() == "true"
        currency = shp_params.get("currency", "RUB")  # Валюта платежа
        
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
                "payment_id": inv_id,  # Используем inv_id как payment_id
                "pair_id": pair_id,
                "amount": out_sum,
                "currency": currency,
                "period_days": int(period_days) if period_days else None,
                "is_lifetime": is_lifetime,
                "status": "succeeded",
            }
