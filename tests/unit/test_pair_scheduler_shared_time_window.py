from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from src.worker.services.pair_scheduler import PairScheduler


@dataclass
class _DailyState:
    morning_initiator: int | None = None
    evening_initiator: int | None = None


class _FakeDailyStateRepo:
    async def get_or_create(self, _pair_id: int, _day: date) -> _DailyState:
        return _DailyState()


class _FakeLockService:
    async def get_key(self, _key: str) -> str | None:
        return None

    async def set_key_with_ttl(self, _key: str, _value: str, _ttl: int) -> bool:
        return True

    async def get_redis_client(self) -> object:  # pragma: no cover
        return object()


class _FakeMessenger:
    async def send_message(self, *args: object, **kwargs: object) -> object:  # pragma: no cover
        raise NotImplementedError

    async def send_photo(self, *args: object, **kwargs: object) -> object:  # pragma: no cover
        raise NotImplementedError

    async def edit_message(self, *args: object, **kwargs: object) -> object:  # pragma: no cover
        raise NotImplementedError

    async def remove_reply_markup(self, *args: object, **kwargs: object) -> object:  # pragma: no cover
        raise NotImplementedError

    async def delete_message(self, *args: object, **kwargs: object) -> bool:  # pragma: no cover
        raise NotImplementedError


@pytest.mark.asyncio
async def test_should_prompt_user_inside_personal_window() -> None:
    scheduler = PairScheduler(
        session=object(), telegram_messenger=_FakeMessenger(), lock_service=_FakeLockService()
    )
    scheduler.daily_state_repo = _FakeDailyStateRepo()  # type: ignore[assignment]

    user = SimpleNamespace(
        id=1,
        utc_offset=3,
        morning_window_start_hour=7,
        evening_window_start_hour=21,
    )
    now_utc = datetime(2026, 1, 20, 4, 30, 0)  # 07:30 MSK

    should, reason, ctx = await scheduler.should_prompt_user(
        user=user,
        pic_type="morning",
        today=date(2026, 1, 20),
        now_utc=now_utc,
    )

    assert should is True
    assert reason == "eligible"
    assert ctx is not None


@pytest.mark.asyncio
async def test_should_prompt_user_outside_personal_window() -> None:
    scheduler = PairScheduler(
        session=object(), telegram_messenger=_FakeMessenger(), lock_service=_FakeLockService()
    )
    scheduler.daily_state_repo = _FakeDailyStateRepo()  # type: ignore[assignment]

    user = SimpleNamespace(
        id=1,
        utc_offset=3,
        morning_window_start_hour=8,
        evening_window_start_hour=22,
    )
    now_utc = datetime(2026, 1, 20, 4, 30, 0)  # 07:30 MSK

    should, reason, ctx = await scheduler.should_prompt_user(
        user=user,
        pic_type="morning",
        today=date(2026, 1, 20),
        now_utc=now_utc,
    )

    assert should is False
    assert reason == "outside_time_window"
    assert ctx is None


@pytest.mark.asyncio
async def test_check_pair_needs_wish_prompt_skips_already_sent() -> None:
    scheduler = PairScheduler(
        session=object(), telegram_messenger=_FakeMessenger(), lock_service=_FakeLockService()
    )

    class _SentRepo(_FakeDailyStateRepo):
        async def get_or_create(self, _pair_id: int, _day: date) -> _DailyState:
            return _DailyState(morning_initiator=99)

    scheduler.daily_state_repo = _SentRepo()  # type: ignore[assignment]
    pair = SimpleNamespace(id=1, status="active")

    ok, reason = await scheduler.check_pair_needs_wish_prompt(
        pair=pair,
        pic_type="morning",
        today=date(2026, 1, 20),
    )

    assert ok is False
    assert reason == "already_sent_today"
