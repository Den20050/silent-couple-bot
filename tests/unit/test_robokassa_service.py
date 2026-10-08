"""Characterization tests for RobokassaService.

These pin the exact wire format Robokassa expects (OutSum format, InvId
constraints, signature string layout, URL parameter set) so refactoring
cannot silently change what is sent to the payment gateway.
"""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest

from src.core.config import Settings
from src.services.payment.robokassa_service import RobokassaService


def make_settings(**overrides) -> Settings:
    values = dict(
        tg_bot_token="test-token",
        database_url="postgresql+asyncpg://u:p@localhost:5432/db",
        demo_pair_hash_salt="salt",
        robokassa_merchant_login="shop",
        robokassa_password_1="pass1",
        robokassa_password_2="pass2",
        robokassa_is_production=True,
        robokassa_domain="robokassa.ru",
        robokassa_result_url=None,
        webhook_url=None,
    )
    values.update(overrides)
    return Settings(**values)


def make_service(**settings_overrides) -> RobokassaService:
    return RobokassaService(redis=None, settings=make_settings(**settings_overrides))


def md5_upper(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest().upper()


def query_params(payment_url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(payment_url).query)


@pytest.fixture
def frozen_ids(monkeypatch: pytest.MonkeyPatch) -> str:
    """Freeze time/random so the InvId generator is deterministic."""
    monkeypatch.setattr(
        "src.services.payment.robokassa_service.time.time", lambda: 1_000_000.0
    )
    monkeypatch.setattr(
        "src.services.payment.robokassa_service.random.randint", lambda a, b: 7
    )
    return "1000000027"  # 1000000 * 1000 + (pair_id=2 % 1000) * 10 + 7


class TestPaymentSignature:
    def test_rub_format(self):
        service = make_service()
        signature = service._generate_payment_signature(
            merchant_login="shop",
            out_sum="299.00",
            inv_id="1000000027",
            password="pass1",
            currency="RUB",
        )
        assert signature == md5_upper("shop:299.00:1000000027:pass1")

    def test_non_rub_includes_currency(self):
        service = make_service()
        signature = service._generate_payment_signature(
            merchant_login="shop",
            out_sum="5.00",
            inv_id="42",
            password="pass1",
            currency="USD",
        )
        assert signature == md5_upper("shop:5.00:42:USD:pass1")

    def test_shp_params_sorted_with_separator(self):
        service = make_service()
        signature = service._generate_payment_signature(
            merchant_login="shop",
            out_sum="299.00",
            inv_id="42",
            password="pass1",
            currency="RUB",
            shp_params={"Shp_b": "2", "Shp_a": "1"},
        )
        assert signature == md5_upper("shop:299.00:42:pass1:Shp_a=1:Shp_b=2")

        signature_alt = service._generate_payment_signature(
            merchant_login="shop",
            out_sum="299.00",
            inv_id="42",
            password="pass1",
            currency="RUB",
            shp_params={"Shp_a": "1"},
            shp_kv_separator=":",
        )
        assert signature_alt == md5_upper("shop:299.00:42:pass1:Shp_a:1")


class TestCreatePayment:
    async def test_production_rub(self, frozen_ids: str):
        service = make_service()
        payment = await service.create_payment(
            amount=29900,  # kopecks
            pair_id=2,
            return_url="https://t.me/bot",
            period_days=30,
        )

        assert payment is not None
        assert payment["id"] == frozen_ids
        assert payment["metadata"] == {
            "pair_id": "2",
            "period_days": "30",
            "is_lifetime": "false",
        }

        params = query_params(payment["confirmation"]["confirmation_url"])
        assert params["MrchLogin"] == ["shop"]
        assert params["OutSum"] == ["299.00"]
        assert params["InvId"] == [frozen_ids]
        assert params["Culture"] == ["ru"]
        assert params["Encoding"] == ["utf-8"]
        assert params["SuccessURL"] == ["https://t.me/bot"]
        assert params["FailURL"] == ["https://t.me/bot"]
        assert "IsTest" not in params  # production mode
        assert "OutSumCurrency" not in params  # RUB must not send it
        assert params["Shp_currency"] == ["RUB"]
        assert params["Shp_is_lifetime"] == ["false"]
        assert params["Shp_pair_id"] == ["2"]
        assert params["Shp_period_days"] == ["30"]

        expected = md5_upper(
            f"shop:299.00:{frozen_ids}:pass1"
            ":Shp_currency=RUB:Shp_is_lifetime=false:Shp_pair_id=2:Shp_period_days=30"
        )
        assert params["SignatureValue"] == [expected]

    async def test_test_mode_formats_out_sum_as_integer(self, frozen_ids: str):
        service = make_service(robokassa_is_production=False)
        payment = await service.create_payment(
            amount=29900, pair_id=2, return_url="https://t.me/bot", period_days=30
        )

        params = query_params(payment["confirmation"]["confirmation_url"])
        assert params["OutSum"] == ["299"]  # test mode: integer, no decimals
        assert params["IsTest"] == ["1"]
        expected = md5_upper(
            f"shop:299:{frozen_ids}:pass1:Shp_currency=RUB"
            ":Shp_is_lifetime=false:Shp_pair_id=2:Shp_period_days=30"
        )
        assert params["SignatureValue"] == [expected]

    async def test_non_rub_sends_out_sum_currency(self, frozen_ids: str):
        service = make_service()
        payment = await service.create_payment(
            amount=500,  # cents
            pair_id=2,
            return_url="https://t.me/bot",
            period_days=30,
            currency="USD",
        )

        params = query_params(payment["confirmation"]["confirmation_url"])
        assert params["OutSum"] == ["5.00"]
        assert params["OutSumCurrency"] == ["USD"]
        assert params["Shp_currency"] == ["USD"]
        expected = md5_upper(
            f"shop:5.00:{frozen_ids}:USD:pass1"
            ":Shp_currency=USD:Shp_is_lifetime=false:Shp_pair_id=2:Shp_period_days=30"
        )
        assert params["SignatureValue"] == [expected]

    async def test_lifetime_metadata(self, frozen_ids: str):
        service = make_service()
        payment = await service.create_payment(
            amount=1000000,
            pair_id=2,
            return_url="https://t.me/bot",
            period_days=999999,
            is_lifetime=True,
        )

        assert payment["metadata"]["is_lifetime"] == "true"
        params = query_params(payment["confirmation"]["confirmation_url"])
        assert params["Shp_is_lifetime"] == ["true"]
        assert params["Shp_period_days"] == ["0"]

    async def test_result_url_derived_from_webhook_url(self, frozen_ids: str):
        service = make_service(webhook_url="https://example.com/webhook/telegram")
        payment = await service.create_payment(
            amount=29900, pair_id=2, return_url="https://t.me/bot"
        )
        params = query_params(payment["confirmation"]["confirmation_url"])
        assert params["ResultURL"] == ["https://example.com/webhook/robokassa"]

    async def test_none_when_circuit_breaker_open(self):
        service = make_service()
        service.circuit_breaker.is_open = AsyncMock(return_value=True)  # type: ignore[method-assign]
        payment = await service.create_payment(
            amount=29900, pair_id=2, return_url="https://t.me/bot"
        )
        assert payment is None


class TestWebhook:
    async def test_process_webhook_valid_signature(self):
        service = make_service()
        shp = {
            "currency": "RUB",
            "is_lifetime": "false",
            "pair_id": "2",
            "period_days": "30",
        }
        inv_id = "1000000027"
        signature = md5_upper(
            f"299.00:{inv_id}:pass2:Shp_currency=RUB"
            ":Shp_is_lifetime=false:Shp_pair_id=2:Shp_period_days=30"
        )

        result = await service.process_webhook("299.00", inv_id, signature, shp)

        assert result == {
            "payment_id": inv_id,
            "pair_id": 2,
            "amount": "299.00",
            "currency": "RUB",
            "period_days": 30,
            "is_lifetime": False,
            "status": "succeeded",
        }

    async def test_process_webhook_invalid_signature_returns_none(self):
        service = make_service()
        result = await service.process_webhook(
            "299.00", "1000000027", "deadbeef", {"pair_id": "2"}
        )
        assert result is None

    async def test_process_webhook_lifetime_has_no_period(self):
        service = make_service()
        shp = {"pair_id": "2", "is_lifetime": "true", "currency": "RUB"}
        signature = md5_upper(
            "1.00:42:pass2:Shp_currency=RUB" ":Shp_is_lifetime=true:Shp_pair_id=2"
        )
        result = await service.process_webhook("1.00", "42", signature, shp)
        assert result is not None
        assert result["is_lifetime"] is True
        assert result["period_days"] is None
