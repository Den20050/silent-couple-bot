from datetime import date

from src.core.messages import get_message
from src.worker.services.notification_builder import NotificationBuilder


class _FakeMessenger:
    async def send_message(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


async def test_warning_silent_under_24h_does_not_use_24h_text() -> None:
    builder = NotificationBuilder(messenger=_FakeMessenger())
    text, _kb = await builder.build_warning_message(
        pair_mode="silent",
        partner_label="@user",
        hours=14,
        pair_id=1,
        target_day=date(2026, 1, 19),
        pic_type="morning",
    )
    assert text == get_message("WARNING_SILENT_MODE", username="user")


async def test_warning_silent_24h_uses_24h_text() -> None:
    builder = NotificationBuilder(messenger=_FakeMessenger())
    text, _kb = await builder.build_warning_message(
        pair_mode="silent",
        partner_label="@user",
        hours=24,
        pair_id=1,
        target_day=date(2026, 1, 19),
        pic_type="morning",
    )
    assert text == get_message("WARNING_24H_SILENT", recipient_name="@user")

