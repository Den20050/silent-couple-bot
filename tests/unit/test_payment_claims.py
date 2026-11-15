from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.repositories.pair_first_payment_bonus import PairFirstPaymentBonusRepository
from src.db.repositories.pair_payments import PairPaymentsRepository


@pytest.mark.asyncio
@pytest.mark.parametrize(("returned", "claimed"), [("invoice-1", True), (None, False)])
async def test_payment_record_is_an_atomic_claim(returned, claimed) -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = returned
    session.execute.return_value = result

    actual = await PairPaymentsRepository(session).record_payment(
        pair_id=1,
        payer_id=2,
        inv_id="invoice-1",
        amount=Decimal("100.00"),
        currency="RUB",
        plan_id="1_month",
        is_lifetime=False,
    )

    assert actual is claimed


@pytest.mark.asyncio
@pytest.mark.parametrize(("returned", "claimed"), [("hash", True), (None, False)])
async def test_bonus_mark_used_is_an_atomic_claim(returned, claimed) -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = returned
    session.execute.return_value = result

    assert await PairFirstPaymentBonusRepository(session).mark_used(1, 2) is claimed
