"""Unit tests for CurrencyRatesService caching behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.payment.currency_rates import CurrencyRatesService


@pytest.mark.asyncio
async def test_get_cached_rate_returns_float_when_redis_returns_bytes() -> None:
    """Ensure cached rate is parsed correctly when Redis returns bytes."""
    redis = AsyncMock()
    redis.get.return_value = b"0.0123"
    settings = MagicMock()
    service = CurrencyRatesService(redis=redis, settings=settings)

    rate = await service._get_cached_rate("USD")

    assert rate == 0.0123


@pytest.mark.asyncio
async def test_get_cached_rate_returns_float_when_redis_returns_str() -> None:
    """Ensure cached rate is parsed correctly when Redis returns str."""
    redis = AsyncMock()
    redis.get.return_value = "0.045"
    settings = MagicMock()
    service = CurrencyRatesService(redis=redis, settings=settings)

    rate = await service._get_cached_rate("USD")

    assert rate == 0.045


@pytest.mark.asyncio
async def test_get_cached_rate_returns_none_when_cache_empty() -> None:
    """Ensure cache miss returns None."""
    redis = AsyncMock()
    redis.get.return_value = None
    settings = MagicMock()
    service = CurrencyRatesService(redis=redis, settings=settings)

    rate = await service._get_cached_rate("USD")

    assert rate is None

