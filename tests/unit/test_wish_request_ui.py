from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.messaging.ui.wish_request_ui import WishRequestUIService


def _user(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "id": 10,
        "tg_id": 100,
        "username": None,
        "utc_offset": 3,
        "morning_window_start_hour": 7,
        "evening_window_start_hour": 21,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_build_for_user_renders_partner_buttons_with_sent_state() -> None:
    session = MagicMock()
    service = WishRequestUIService(session=session)  # type: ignore[arg-type]

    user = _user()
    partner = SimpleNamespace(id=11, tg_id=200, username="partner")
    day = date(2026, 1, 18)
    now_utc = datetime(2026, 1, 18, 8, 0, 0)  # 11:00 MSK, morning send period open

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
        user_tg_id=100, pic_type="morning", day=day, now_utc=now_utc
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

    user = _user()
    partner = SimpleNamespace(id=11, tg_id=200, username="p1")
    day = date(2026, 8, 12)
    now_utc = datetime(2026, 8, 12, 18, 30, 0)  # 21:30 MSK, evening send period open

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
        user_tg_id=100, pic_type="evening", day=day, now_utc=now_utc
    )

    keyboard = ui.reply_markup["inline_keyboard"]
    assert len(keyboard) == 2


@pytest.mark.asyncio
async def test_build_for_user_renders_pay_button_for_past_due_pair() -> None:
    session = MagicMock()
    service = WishRequestUIService(session=session)  # type: ignore[arg-type]

    user = _user()
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
        user_tg_id=100,
        pic_type="evening",
        day=date(2026, 1, 18),
        now_utc=datetime(2026, 1, 18, 18, 0, 0),
    )

    keyboard = ui.reply_markup["inline_keyboard"]
    assert len(keyboard) == 1
    btn = keyboard[0][0]
    assert btn["callback_data"] == "wish_pay_evening_3"
    assert btn["text"].startswith("💳")


@pytest.mark.asyncio
async def test_build_for_user_hides_send_buttons_when_period_closed() -> None:
    session = MagicMock()
    service = WishRequestUIService(session=session)  # type: ignore[arg-type]

    user = _user()
    partner = SimpleNamespace(id=11, tg_id=200, username="p1")
    pair = SimpleNamespace(
        id=14, uid_a=10, uid_b=11, status="active", nickname_a=None, nickname_b=None
    )

    service._users_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_by_tg_id=AsyncMock(return_value=user),
        get_by_id=AsyncMock(return_value=partner),
    )
    service._pairs_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_all_by_user_tg_id=AsyncMock(return_value=[pair]),
        get_my_nickname_for_partner=MagicMock(return_value=None),
    )
    service._daily_state_repo = SimpleNamespace(  # type: ignore[attr-defined]
        get_or_create=AsyncMock(
            return_value=SimpleNamespace(morning_initiator=None, evening_initiator=None)
        )
    )

    # 22:00 MSK — morning send period already closed
    ui = await service.build_for_user(
        user_tg_id=100,
        pic_type="morning",
        day=date(2026, 8, 12),
        now_utc=datetime(2026, 8, 12, 19, 0, 0),
    )

    assert ui.reply_markup["inline_keyboard"] == []
