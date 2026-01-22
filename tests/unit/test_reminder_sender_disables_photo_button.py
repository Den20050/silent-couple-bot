from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from src.worker.services.reminder_sender import ReminderSender


class _FakeRedis:
    def __init__(self, store: dict[str, str]) -> None:
        self.store = store
        self.deleted: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.store.pop(key, None)


class _FakeMessenger:
    def __init__(self) -> None:
        self.removed: list[tuple[int, int]] = []

    async def remove_reply_markup(self, chat_id: int, message_id: int) -> Any:
        self.removed.append((chat_id, message_id))
        return SimpleNamespace(message_id=message_id)

    async def send_message(self, *args: object, **kwargs: object) -> Any:  # pragma: no cover
        return SimpleNamespace(message_id=1)


class _FakeNotificationBuilder:
    async def build_reminder_message(self, *args: object, **kwargs: object) -> tuple[str, dict]:
        return "text", {"inline_keyboard": [[{"text": "OK", "callback_data": "x"}]]}

    async def build_aggregated_reminder_message(self, *args: object, **kwargs: object) -> tuple[str, dict]:
        return "text", {"inline_keyboard": [[{"text": "OK", "callback_data": "x"}]]}


@dataclass
class _Candidate:
    pair: Any
    recipient: Any
    initiator: Any
    target_day: date
    pic_type: str


@pytest.mark.asyncio
async def test_send_reminder_disables_wish_photo_button(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.services.messaging.wish_photo_message_id import wish_photo_message_id_key

    recipient = SimpleNamespace(tg_id=100, id=1)
    initiator = SimpleNamespace(tg_id=200, username="init")
    pair = SimpleNamespace(id=10, uid_a=1, uid_b=2, nickname_a=None, nickname_b=None, mode="silent")
    target_day = date(2026, 1, 20)

    key = wish_photo_message_id_key(tg_id=recipient.tg_id, pair_id=pair.id, pic_type="morning", day=target_day)

    worker_context = SimpleNamespace(
        messenger=_FakeMessenger(),
        notification_builder=_FakeNotificationBuilder(),
        redis=_FakeRedis({key: "777"}),
    )

    sender = ReminderSender(worker_context=worker_context)

    candidate = _Candidate(
        pair=pair,
        recipient=recipient,
        initiator=initiator,
        target_day=target_day,
        pic_type="morning",
    )

    # Fake lock service
    class _Lock:
        async def set_key_with_ttl(self, *args: object, **kwargs: object) -> None:
            return None

    await sender.send_reminder(candidate=candidate, reminder_key="rk", lock_service=_Lock())

    assert worker_context.messenger.removed == [(recipient.tg_id, 777)]

