from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.messaging.ui.wish_request_ui import WishRequestUIService


@pytest.mark.asyncio
async def test_build_for_user_renders_partner_buttons_with_sent_state() -> None:
    # given
    session = MagicMock()
    service = WishRequestUIService(session=session)  # type: ignore[arg-type]

    user = SimpleNamespace(id=10, tg_id=100, username=None)
    partner = SimpleNamespace(id=11, tg_id=200, username="partner")

    pair_pending = SimpleNamespace(
        id=1, uid_a=10, uid_b=11, status="active", nickname_a=None, nickname_b=None
    )
    pair_sent = SimpleNamespace(
        id=2, uid_a=10, uid_b=11, status="trial", nickname_a=None, nickname_b=None
    )

    service._users_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_by_tg_id=AsyncMock(return_value=user),
        get_by_id=AsyncMock(return_value=partner),
    )
    service._pairs_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_all_by_user_tg_id=AsyncMock(return_value=[pair_pending, pair_sent]),
        get_my_nickname_for_partner=MagicMock(return_value=None),
    )
    service._daily_state_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_or_create=AsyncMock(
            side_effect=[
                SimpleNamespace(morning_initiator=None, evening_initiator=None),
                SimpleNamespace(morning_initiator=999, evening_initiator=None),
            ]
        )
    )

    # when
    ui = await service.build_for_user(
        user_tg_id=100, pic_type="morning", day=date(2026, 1, 18)
    )

    # then
    assert "Утро" in ui.text
    keyboard = ui.reply_markup["inline_keyboard"]
    assert len(keyboard) == 2

    pending_btn = keyboard[0][0]
    assert pending_btn["callback_data"] == "request_morning_1_10"
    assert pending_btn["text"].startswith("📨")

    sent_btn = keyboard[1][0]
    assert sent_btn["callback_data"] == "wish_sent_morning_2"
    assert sent_btn["text"].startswith("✅")

