from datetime import date

from src.core.messages import get_message
from src.worker.services.notification_builder import NotificationBuilder


class _FakeMessenger:
    async def send_message(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


async def test_reminder_silent_with_label_uses_with_nickname_template() -> None:
    builder = NotificationBuilder(messenger=_FakeMessenger())
    text, _kb = await builder.build_reminder_message(
        pair_mode="silent",
        pic_type="morning",
        pair_id=1,
        initiator_tg_id=10,
        target_day=date(2026, 1, 19),
        initiator_label="Мама",
    )
    assert text == get_message("REMINDER_SILENT_MODE_WITH_NICKNAME", nickname="Мама")


async def test_reminder_chat_without_label_uses_base_template() -> None:
    builder = NotificationBuilder(messenger=_FakeMessenger())
    text, _kb = await builder.build_reminder_message(
        pair_mode="chat",
        pic_type="evening",
        pair_id=1,
        initiator_tg_id=10,
        target_day=date(2026, 1, 19),
        initiator_label=None,
    )
    assert text == get_message("REMINDER_CHAT_MODE")

