"""Currency exchange rates service with caching."""

from typing import Optional

from redis.asyncio import Redis

from src.core.config import Settings
from src.core.constants import SUPPORTED_CURRENCIES
from src.core.logger import get_logger

logger = get_logger(__name__)


class CurrencyRatesService:
    """Service for fetching and caching currency exchange rates.
    
    Uses external API (e.g., ЦБ РФ) to get actual exchange rates,
    caches them in Redis for a configurable period.
    """
    
    def __init__(self, redis: Redis | None, settings: Settings) -> None:
        """Initialize currency rates service.
        
        Args:
            redis: Redis client for caching (optional)
            settings: Application settings
        """
        self.redis = redis
        self.settings = settings
        self._cache_ttl_seconds = getattr(settings, 'currency_rates_cache_ttl_minutes', 30) * 60
    
    async def get_rate(self, currency_code: str) -> Optional[float]:
        """Get exchange rate for currency (RUB to currency).
        
        Args:
            currency_code: Currency code (e.g., "USD", "EUR")
            
        Returns:
            Exchange rate (how many currency units per 1 RUB), or None if not available
        """
        if currency_code == "RUB":
            return 1.0
        
        # Try to get from cache first
        cached_rate = await self._get_cached_rate(currency_code)
        if cached_rate is not None:
            return cached_rate
        
        # Fetch fresh rate from API
        rate = await self._fetch_rate_from_api(currency_code)
        if rate is not None:
            await self._cache_rate(currency_code, rate)
            return rate
        
        # Fallback to config exchange rates if API fails
        logger.warning(
            "Failed to fetch rate from API, using config fallback",
            currency_code=currency_code,
        )
        return self._get_config_rate(currency_code)
    
    async def _get_cached_rate(self, currency_code: str) -> Optional[float]:
        """Get cached exchange rate from Redis.
        
        Args:
            currency_code: Currency code
            
        Returns:
            Cached rate or None if not cached/expired
        """
        if not self.redis:
            return None
        
        try:
            cache_key = f"currency_rate:{currency_code}"
            cached_value = await self.redis.get(cache_key)
            if cached_value:
                return float(cached_value.decode())
        except Exception as e:
            logger.warning(
                "Failed to get cached rate",
                currency_code=currency_code,
                error=str(e),
            )
        
        return None
    
    async def _cache_rate(self, currency_code: str, rate: float) -> None:
        """Cache exchange rate in Redis.
        
        Args:
            currency_code: Currency code
            rate: Exchange rate
        """
        if not self.redis:
            return
        
        try:
            cache_key = f"currency_rate:{currency_code}"
            await self.redis.setex(
                cache_key,
                self._cache_ttl_seconds,
                str(rate),
            )
            logger.debug(
                "Cached currency rate",
                currency_code=currency_code,
                rate=rate,
                ttl_seconds=self._cache_ttl_seconds,
            )
        except Exception as e:
            logger.warning(
                "Failed to cache rate",
                currency_code=currency_code,
                error=str(e),
            )
    
    async def _fetch_rate_from_api(self, currency_code: str) -> Optional[float]:
        """Fetch exchange rate from external API.
        
        Currently uses ЦБ РФ API for RUB-based rates.
        For other currencies, calculates from USD/EUR rates.
        
        Args:
            currency_code: Currency code
            
        Returns:
            Exchange rate or None if fetch failed
        """
        try:
            # ЦБ РФ API: https://www.cbr.ru/development/sxml/
            # For now, we'll use a simple approach: fetch USD and EUR rates,
            # then calculate other currencies from them
            
            # For USD and EUR, fetch directly from ЦБ РФ
            if currency_code in ("USD", "EUR"):
                rate = await self._fetch_cbr_rate(currency_code)
                if rate:
                    # CBR returns rate as "how many RUB per 1 currency unit"
                    # We need "how many currency units per 1 RUB"
                    return 1.0 / rate
            
            # For other currencies, use config rates as fallback
            # (or implement calculation from USD/EUR if needed)
            return self._get_config_rate(currency_code)
            
        except Exception as e:
            logger.error(
                "Failed to fetch rate from API",
                currency_code=currency_code,
                error=str(e),
                exc_info=True,
            )
            return None
    
    async def _fetch_cbr_rate(self, currency_code: str) -> Optional[float]:
        """Fetch exchange rate from ЦБ РФ API.
        
        Args:
            currency_code: Currency code (USD or EUR)
            
        Returns:
            Rate as "RUB per 1 currency unit", or None if failed
        """
        try:
            import httpx
            
            # ЦБ РФ API endpoint
            # Format: https://www.cbr.ru/scripts/XML_daily.asp
            # Returns XML with daily rates
            url = "https://www.cbr.ru/scripts/XML_daily.asp"
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(
                        "CBR API returned non-200 status",
                        status=response.status_code,
                        currency_code=currency_code,
                    )
                    return None
                
                # Parse XML response
                import xml.etree.ElementTree as ET
                content = response.text
                root = ET.fromstring(content)
                
                # Find currency in XML
                # CBR uses ISO codes: USD -> 840, EUR -> 978
                currency_map = {
                    "USD": "840",
                    "EUR": "978",
                }
                char_code = currency_map.get(currency_code)
                if not char_code:
                    return None
                
                # Find Valute element with matching CharCode
                for valute in root.findall(".//Valute"):
                    if valute.find("CharCode").text == currency_code:
                        # Get Value (e.g., "75.50" for USD)
                        value_str = valute.find("Value").text
                        # CBR uses comma as decimal separator
                        value_str = value_str.replace(",", ".")
                        rate = float(value_str)
                        # CBR returns rate for 1 unit of currency
                        return rate
            
            return None
        except ImportError:
            logger.warning("httpx not available, cannot fetch rates from API")
            return None
        except Exception as e:
            logger.warning(
                "Failed to fetch CBR rate",
                currency_code=currency_code,
                error=str(e),
            )
            return None
    
    def _get_config_rate(self, currency_code: str) -> Optional[float]:
        """Get exchange rate from config (fallback).
        
        Args:
            currency_code: Currency code
            
        Returns:
            Exchange rate from config, or None if not found
        """
        exchange_rates = self.settings.get_currency_exchange_rates()
        return exchange_rates.get(currency_code)
    
    async def calculate_price_in_currency(
        self,
        rub_price: float,
        currency_code: str,
    ) -> float:
        """Calculate price in target currency from RUB price.
        
        Uses actual exchange rate and applies margin.
        
        Args:
            rub_price: Price in RUB
            currency_code: Target currency code
            
        Returns:
            Price in target currency
        """
        if currency_code == "RUB":
            return rub_price
        
        # Get exchange rate
        rate = await self.get_rate(currency_code)
        rate_source = "API/cache"
        if not rate:
            # Fallback to config rate
            rate = self._get_config_rate(currency_code) or 1.0
            rate_source = "config"
        
        # Apply margin
        margin_percent = self.settings.currency_margin_percent
        margin_multiplier = 1.0 + (margin_percent / 100.0)
        
        # Calculate: price = RUB_price * rate * margin
        calculated_price = rub_price * rate * margin_multiplier
        
        # Log calculation for debugging
        logger.debug(
            "Calculating price in currency",
            currency_code=currency_code,
            rub_price=rub_price,
            exchange_rate=rate,
            rate_source=rate_source,
            margin_percent=margin_percent,
            calculated_price=calculated_price,
        )
        
        # Round to appropriate decimals
        decimals = SUPPORTED_CURRENCIES.get(currency_code, SUPPORTED_CURRENCIES["RUB"])["decimals"]
        
        # Round to 2 decimals for most currencies, or to 5 cents for some
        if decimals == 2:
            # Round to nearest cent
            return round(calculated_price, 2)
        else:
            return round(calculated_price, decimals)

