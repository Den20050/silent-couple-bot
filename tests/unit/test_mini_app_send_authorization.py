from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.mini_app.routes import _authorize_send


def _result(*, scalar=None, scalars=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    result.scalars.return_value.all.return_value = scalars or []
    return result


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.execute_count = 0

    async def execute(self, _statement):
        self.execute_count += 1
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_authorize_send_accepts_owned_pair_chat_and_pool_picture() -> None:
    user = SimpleNamespace(id=1)
    pair = SimpleNamespace(
        uid_a=1,
        uid_b=2,
        status="active",
        delivery_chat="pair_dm",
        private_chat_id=-100123,
    )
    session = _Session([
        _result(scalar=user),
        _result(scalars=[pair]),
        _result(scalar="morning"),
    ])

    assert await _authorize_send(
        session, tg_id=123, chat_id=-100123, file_id="known"
    ) == "morning"


@pytest.mark.asyncio
async def test_authorize_send_rejects_outsider_chat_before_picture_lookup() -> None:
    user = SimpleNamespace(id=1)
    pair = SimpleNamespace(
        uid_a=1,
        uid_b=2,
        status="active",
        delivery_chat="pair_dm",
        private_chat_id=-100123,
    )
    session = _Session([_result(scalar=user), _result(scalars=[pair])])

    assert await _authorize_send(
        session, tg_id=123, chat_id=-999, file_id="known"
    ) is None
    assert session.execute_count == 2
