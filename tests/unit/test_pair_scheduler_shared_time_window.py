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
async def test_send_wish_uses_pair_window_after_owner_set() -> None:
    """If a pair has an owner, the pair-level window is used (shared for both users)."""

    scheduler = PairScheduler(
        session=object(), telegram_messenger=_FakeMessenger(), lock_service=_FakeLockService()
    )
    # Patch repos (we're unit-testing window logic only).
    scheduler.daily_state_repo = _FakeDailyStateRepo()  # type: ignore[assignment]

    pair = SimpleNamespace(
        id=1,
        status="trial",
        # Shared windows become active only when owner is set:
        notification_window_owner_id=10,
        morning_window_start_hour=6,
        evening_window_start_hour=21,
    )

    # now_utc 03:30, user_a utc+3 => 06:30 (in 06–07 window)
    now_utc = datetime(2026, 1, 20, 3, 30, 0)
    user_a = SimpleNamespace(utc_offset=3, morning_window_start_hour=8, evening_window_start_hour=22)
    user_b = SimpleNamespace(utc_offset=0, morning_window_start_hour=8, evening_window_start_hour=22)

    eligible, reason, attempt_ctx = await scheduler.send_wish_for_pair(
        pair=pair,
        user_a=user_a,
        user_b=user_b,
        pic_type="morning",
        today=date(2026, 1, 20),
        now_utc=now_utc,
    )

    assert eligible is True
    assert reason == "eligible"
    assert attempt_ctx is not None


@pytest.mark.asyncio
async def test_send_wish_uses_user_windows_when_owner_not_set() -> None:
    """If owner is not set, per-user windows remain in effect (backward compatible)."""

    scheduler = PairScheduler(
        session=object(), telegram_messenger=_FakeMessenger(), lock_service=_FakeLockService()
    )
    scheduler.daily_state_repo = _FakeDailyStateRepo()  # type: ignore[assignment]

    pair = SimpleNamespace(
        id=1,
        status="trial",
        notification_window_owner_id=None,
        # Even if pair fields exist, they are ignored until owner is set:
        morning_window_start_hour=6,
        evening_window_start_hour=21,
    )

    # now_utc 03:30, user local 06:30, but both users chose 08–09 => outside.
    now_utc = datetime(2026, 1, 20, 3, 30, 0)
    user_a = SimpleNamespace(utc_offset=3, morning_window_start_hour=8, evening_window_start_hour=22)
    user_b = SimpleNamespace(utc_offset=3, morning_window_start_hour=8, evening_window_start_hour=22)

    eligible, reason, attempt_ctx = await scheduler.send_wish_for_pair(
        pair=pair,
        user_a=user_a,
        user_b=user_b,
        pic_type="morning",
        today=date(2026, 1, 20),
        now_utc=now_utc,
    )

    assert eligible is False
    assert reason == "outside_time_window"
    assert attempt_ctx is None


@pytest.mark.asyncio
async def test_send_wish_eligible_when_jitter_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pair is eligible once its daily jitter has elapsed inside the window."""
    import src.worker.services.pair_scheduler as pair_scheduler_module

    # Pin jitter to 0 so the pair is always ready the moment the window opens.
    monkeypatch.setattr(
        pair_scheduler_module,
        "_pair_daily_jitter_minutes",
        lambda *_args, **_kwargs: 0,
    )

    scheduler = PairScheduler(
        session=object(), telegram_messenger=_FakeMessenger(), lock_service=_FakeLockService()
    )
    scheduler.daily_state_repo = _FakeDailyStateRepo()  # type: ignore[assignment]

    pair = SimpleNamespace(
        id=1,
        status="trial",
        notification_window_owner_id=10,
        morning_window_start_hour=6,
        evening_window_start_hour=21,
    )
    # now_utc 03:31, user_a utc+3 => 06:31 (in 06–07 window, 31 min elapsed)
    now_utc = datetime(2026, 1, 20, 3, 31, 0)
    user_a = SimpleNamespace(utc_offset=3, morning_window_start_hour=8, evening_window_start_hour=22)
    user_b = SimpleNamespace(utc_offset=0, morning_window_start_hour=8, evening_window_start_hour=22)

    eligible, reason, attempt_ctx = await scheduler.send_wish_for_pair(
        pair=pair,
        user_a=user_a,
        user_b=user_b,
        pic_type="morning",
        today=date(2026, 1, 20),
        now_utc=now_utc,
    )

    assert eligible is True
    assert reason == "eligible"
    assert attempt_ctx is not None


@pytest.mark.asyncio
async def test_jitter_not_reached_skips_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pair in window is skipped if daily jitter minutes have not elapsed yet."""
    import src.worker.services.pair_scheduler as pair_scheduler_module

    monkeypatch.setattr(
        pair_scheduler_module,
        "_pair_daily_jitter_minutes",
        lambda *_args, **_kwargs: 5,
    )

    scheduler = PairScheduler(
        session=object(), telegram_messenger=_FakeMessenger(), lock_service=_FakeLockService()
    )
    scheduler.daily_state_repo = _FakeDailyStateRepo()  # type: ignore[assignment]

    pair = SimpleNamespace(
        id=1,
        status="trial",
        notification_window_owner_id=10,
        morning_window_start_hour=6,
        evening_window_start_hour=21,
    )
    # now_utc 03:02, user_a utc+3 => 06:02 (2 min into window, jitter=5 => not ready)
    now_utc = datetime(2026, 1, 20, 3, 2, 0)
    user_a = SimpleNamespace(utc_offset=3, morning_window_start_hour=8, evening_window_start_hour=22)
    user_b = SimpleNamespace(utc_offset=0, morning_window_start_hour=8, evening_window_start_hour=22)

    eligible, reason, attempt_ctx = await scheduler.send_wish_for_pair(
        pair=pair,
        user_a=user_a,
        user_b=user_b,
        pic_type="morning",
        today=date(2026, 1, 20),
        now_utc=now_utc,
    )

    assert eligible is False
    assert reason == "jitter_not_reached"
    assert attempt_ctx is None


@pytest.mark.asyncio
async def test_jitter_reached_passes_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pair is eligible once minutes_in_window >= jitter_minutes."""
    import src.worker.services.pair_scheduler as pair_scheduler_module

    monkeypatch.setattr(
        pair_scheduler_module,
        "_pair_daily_jitter_minutes",
        lambda *_args, **_kwargs: 5,
    )

    scheduler = PairScheduler(
        session=object(), telegram_messenger=_FakeMessenger(), lock_service=_FakeLockService()
    )
    scheduler.daily_state_repo = _FakeDailyStateRepo()  # type: ignore[assignment]

    pair = SimpleNamespace(
        id=1,
        status="trial",
        notification_window_owner_id=10,
        morning_window_start_hour=6,
        evening_window_start_hour=21,
    )
    # now_utc 03:36, user_a utc+3 => 06:36 (6 min into window, jitter=5 => ready)
    now_utc = datetime(2026, 1, 20, 3, 36, 0)
    user_a = SimpleNamespace(utc_offset=3, morning_window_start_hour=8, evening_window_start_hour=22)
    user_b = SimpleNamespace(utc_offset=0, morning_window_start_hour=8, evening_window_start_hour=22)

    eligible, reason, attempt_ctx = await scheduler.send_wish_for_pair(
        pair=pair,
        user_a=user_a,
        user_b=user_b,
        pic_type="morning",
        today=date(2026, 1, 20),
        now_utc=now_utc,
    )

    assert eligible is True
    assert reason == "eligible"
    assert attempt_ctx is not None

