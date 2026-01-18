from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.messaging.wish_request_prompt_refresher import refresh_aggregated_wish_prompt


@pytest.mark.asyncio
async def test_refresh_aggregated_wish_prompt_edits_message_when_redis_has_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # given
    redis = MagicMock()
    redis.get = AsyncMock(return_value="123")
    redis.aclose = AsyncMock()

    async def _fake_create_redis_client(*_args, **_kwargs):
        return redis

    import src.core.redis_client as redis_client_module

    monkeypatch.setattr(redis_client_module, "create_redis_client", _fake_create_redis_client)

    session = MagicMock()
    messenger = MagicMock()
    messenger.edit_message = AsyncMock()

    # Patch UI builder to avoid DB usage
    import src.services.messaging.wish_request_prompt_refresher as refresher_module

    fake_ui = MagicMock()
    fake_ui.text = "hello"
    fake_ui.reply_markup = {"inline_keyboard": []}
    fake_builder = MagicMock()
    fake_builder.build_for_user = AsyncMock(return_value=fake_ui)
    monkeypatch.setattr(refresher_module, "WishRequestUIService", MagicMock(return_value=fake_builder))

    # when
    await refresh_aggregated_wish_prompt(
        session=session,  # type: ignore[arg-type]
        telegram_messenger=messenger,  # type: ignore[arg-type]
        tg_id=111,
        pic_type="morning",
        day=date(2026, 1, 18),
    )

    # then
    messenger.edit_message.assert_awaited_once()

