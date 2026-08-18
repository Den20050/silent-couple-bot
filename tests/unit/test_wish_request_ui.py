from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.messaging.ui.wish_request_ui import WishRequestUIService


@pytest.mark.asyncio
async def test_build_for_user_renders_partner_buttons_with_sent_state() -> None:
    session = MagicMock()
    service = WishRequestUIService(session=session)  # type: ignore[arg-type]

    user = SimpleNamespace(id=10, tg_id=100, username=None)
    partner = SimpleNamespace(id=11, tg_id=200, username="partner")
    day = date(2026, 1, 18)

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

    ui = await service.build_for_user(
        user_tg_id=100, pic_type="morning", day=day
    )

    assert "Утро" in ui.text
    keyboard = ui.reply_markup["inline_keyboard"]
    assert len(keyboard) == 2

    pending_btn = keyboard[0][0]
    assert pending_btn["callback_data"] == f"request_morning_1_10|{day.isoformat()}"
    assert pending_btn["text"].startswith("📨")

    sent_btn = keyboard[1][0]
    assert sent_btn["callback_data"] == "wish_sent_morning_2"
    assert sent_btn["text"].startswith("✅")


@pytest.mark.asyncio
async def test_build_for_user_shows_all_unsent_partners() -> None:
    session = MagicMock()
    service = WishRequestUIService(session=session)  # type: ignore[arg-type]

    user = SimpleNamespace(id=10, tg_id=100, username=None)
    partner = SimpleNamespace(id=11, tg_id=200, username="p1")
    day = date(2026, 8, 12)

    pair_a = SimpleNamespace(
        id=17, uid_a=10, uid_b=11, status="active", nickname_a=None, nickname_b=None
    )
    pair_b = SimpleNamespace(
        id=14, uid_a=10, uid_b=11, status="active", nickname_a=None, nickname_b=None
    )

    service._users_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_by_tg_id=AsyncMock(return_value=user),
        get_by_id=AsyncMock(return_value=partner),
    )
    service._pairs_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_all_by_user_tg_id=AsyncMock(return_value=[pair_a, pair_b]),
        get_my_nickname_for_partner=MagicMock(return_value=None),
    )
    service._daily_state_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_or_create=AsyncMock(
            return_value=SimpleNamespace(morning_initiator=None, evening_initiator=None)
        )
    )

    ui = await service.build_for_user(
        user_tg_id=100, pic_type="evening", day=day
    )

    keyboard = ui.reply_markup["inline_keyboard"]
    assert len(keyboard) == 2


@pytest.mark.asyncio
async def test_build_for_user_renders_pay_button_for_past_due_pair() -> None:
    session = MagicMock()
    service = WishRequestUIService(session=session)  # type: ignore[arg-type]

    user = SimpleNamespace(id=10, tg_id=100, username=None)
    partner = SimpleNamespace(id=11, tg_id=200, username="husband")
    pair_past_due = SimpleNamespace(
        id=3, uid_a=10, uid_b=11, status="past_due", nickname_a=None, nickname_b=None
    )

    service._users_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_by_tg_id=AsyncMock(return_value=user),
        get_by_id=AsyncMock(return_value=partner),
    )
    service._pairs_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_all_by_user_tg_id=AsyncMock(return_value=[pair_past_due]),
        get_my_nickname_for_partner=MagicMock(return_value=None),
    )
    service._daily_state_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_or_create=AsyncMock(),
    )

    ui = await service.build_for_user(
        user_tg_id=100, pic_type="evening", day=date(2026, 1, 18)
    )

    keyboard = ui.reply_markup["inline_keyboard"]
    assert len(keyboard) == 1
    btn = keyboard[0][0]
    assert btn["callback_data"] == "wish_pay_evening_3"
    assert btn["text"].startswith("💳")
