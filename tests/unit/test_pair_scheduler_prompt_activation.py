from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from src.worker.services.pair_scheduler import PairScheduler, WishRequestAttemptContext


@dataclass(frozen=True)
class _UI:
    text: str
    reply_markup: dict[str, Any]


class _FakeWishRequestUIService:
    def __init__(self, _session: object) -> None:
        pass

    async def build_for_user(self, user_tg_id: int, pic_type: str, day: date) -> _UI:
        return _UI(
            text=f"{pic_type}:{day.isoformat()}:{user_tg_id}",
            reply_markup={"inline_keyboard": [[{"text": "OK", "callback_data": "x"}]]},
        )


class _FakeLockService:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int]] = []

    async def get_key(self, key: str) -> str | None:
        return self.store.get(key)

    async def set_key_with_ttl(self, key: str, value: str, ttl_seconds: int) -> bool:
        self.store[key] = value
        self.set_calls.append((key, value, ttl_seconds))
        return True

    async def get_redis_client(self) -> object:
        return object()


class _FakeMessenger:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.edited: list[tuple[int, int]] = []

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
        save_message: bool = True,
    ) -> Any:
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=777)

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str | None = None,
        reply_markup: dict | None = None,
    ) -> Any:
        self.edited.append((chat_id, message_id))
        return None

    async def send_photo(self, *args: object, **kwargs: object) -> Any:  # pragma: no cover
        raise NotImplementedError

    async def remove_reply_markup(self, *args: object, **kwargs: object) -> Any:  # pragma: no cover
        raise NotImplementedError

    async def delete_message(self, *args: object, **kwargs: object) -> bool:  # pragma: no cover
        raise NotImplementedError


@pytest.mark.asyncio
async def test_prompt_send_succeeds_even_if_activation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Activation errors must not make the scheduler resend prompts every minute."""

    # Arrange: replace UI builder and force activate_message to fail.
    import src.worker.services.pair_scheduler as pair_scheduler_module

    monkeypatch.setattr(
        pair_scheduler_module, "WishRequestUIService", _FakeWishRequestUIService
    )

    async def _boom(**_: object) -> None:
        raise TypeError("activate_message() missing 1 required keyword-only argument: 'kind'")

    monkeypatch.setattr(pair_scheduler_module, "activate_message", _boom)

    lock_service = _FakeLockService()
    messenger = _FakeMessenger()

    scheduler = PairScheduler(session=object(), telegram_messenger=messenger, lock_service=lock_service)

    attempt_ctx_by_tg_id = {
        111: WishRequestAttemptContext(
            first_sent_key="k:first",
            last_sent_key="k:last",
            count_key="k:count",
            attempt_count=0,
        )
    }

    # Act
    updated, succeeded = await scheduler.send_aggregated_wish_requests(
        user_to_pair_ids={111: {123}},
        pic_type="evening",
        today=date(2026, 1, 20),
        now_utc=datetime(2026, 1, 20, 18, 0, 0, tzinfo=timezone.utc),
        attempt_ctx_by_tg_id=attempt_ctx_by_tg_id,
    )

    # Assert: prompt was sent once and considered successful despite activation failure.
    assert updated == 1
    assert succeeded == {111}
    assert messenger.sent == [(111, "evening:2026-01-20:111")]
    # Attempt tracking should have been updated (count key set at least once).
    assert any(call[0] == "k:count" for call in lock_service.set_calls)


@pytest.mark.asyncio
async def test_prompt_edit_succeeds_even_if_activation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Activation errors must not make edit-path fail (otherwise we fallback to new sends)."""

    import src.worker.services.pair_scheduler as pair_scheduler_module

    monkeypatch.setattr(
        pair_scheduler_module, "WishRequestUIService", _FakeWishRequestUIService
    )

    async def _boom(**_: object) -> None:
        raise RuntimeError("redis down")

    monkeypatch.setattr(pair_scheduler_module, "activate_message", _boom)

    lock_service = _FakeLockService()
    # Pre-existing prompt message id in Redis, so scheduler should edit.
    lock_service.store["wish_request_prompt_message_id:111:evening:2026-01-20"] = "555"

    messenger = _FakeMessenger()
    scheduler = PairScheduler(session=object(), telegram_messenger=messenger, lock_service=lock_service)

    attempt_ctx_by_tg_id = {
        111: WishRequestAttemptContext(
            first_sent_key="k:first",
            last_sent_key="k:last",
            count_key="k:count",
            attempt_count=1,
        )
    }

    updated, succeeded = await scheduler.send_aggregated_wish_requests(
        user_to_pair_ids={111: {123}},
        pic_type="evening",
        today=date(2026, 1, 20),
        now_utc=datetime(2026, 1, 20, 18, 1, 0, tzinfo=timezone.utc),
        attempt_ctx_by_tg_id=attempt_ctx_by_tg_id,
    )

    assert updated == 1
    assert succeeded == {111}
    assert messenger.edited == [(111, 555)]
    assert messenger.sent == []
