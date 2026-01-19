from datetime import date

from src.core.messages import get_message
from src.worker.services.notification_builder import NotificationBuilder


class _FakeMessenger:
    async def send_message(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


async def test_aggregated_reminder_single_item_uses_singular_text() -> None:
    builder = NotificationBuilder(messenger=_FakeMessenger())
    text, kb = await builder.build_aggregated_reminder_message(
        pair_mode="silent",
        items=[
            {
                "partner_label": "Мама",
                "callback_data": "tap_morning_1_10|2026-01-19",
            }
        ],
    )
    assert text == get_message("REMINDER_SILENT_MODE_WITH_NICKNAME", nickname="Мама")
    assert kb["inline_keyboard"][0][0]["text"] == get_message(
        "RESPOND_BUTTON_WITH_PARTNER",
        partner="Мама",
    )
