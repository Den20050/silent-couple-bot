from src.core.messages import get_message
from src.worker.services.notification_builder import NotificationBuilder


class _FakeMessenger:
    async def send_message(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


async def test_notification_builder_past_due_without_partner_uses_base_message() -> None:
    builder = NotificationBuilder(messenger=_FakeMessenger())
    text, _kb = await builder.build_past_due_notification_message(include_button=False)
    assert text == get_message("WORKER_PAST_DUE_NOTIFICATION")


async def test_notification_builder_past_due_with_partner_uses_labeled_message() -> None:
    builder = NotificationBuilder(messenger=_FakeMessenger())
    text, _kb = await builder.build_past_due_notification_message(
        include_button=False,
        partner_label="Мама",
    )
    assert text == get_message(
        "WORKER_PAST_DUE_NOTIFICATION_WITH_PARTNER",
        partner="Мама",
    )


async def test_notification_builder_dunning_with_partner_uses_labeled_message() -> None:
    builder = NotificationBuilder(messenger=_FakeMessenger())
    text, _kb = await builder.build_dunning_notification_message(partner_label="@someuser")
    assert text == get_message(
        "WORKER_PAST_DUE_DUNNING_WITH_PARTNER",
        partner="@someuser",
    )


async def test_notification_builder_includes_pair_id_in_pay_callback() -> None:
    builder = NotificationBuilder(messenger=_FakeMessenger())
    _text, kb = await builder.build_past_due_notification_message(
        include_button=True,
        partner_label="Мама",
        pair_id=123,
    )
    assert kb is not None
    assert kb["inline_keyboard"][0][0]["callback_data"] == "pay_select_currency_123"

