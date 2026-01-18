from dataclasses import dataclass

from src.services.messaging.ui.menu_ui import MenuUIService


@dataclass(frozen=True)
class _FakeSettings:
    resource_inn: str | None = None
    resource_status: str | None = None
    resource_ogrn: str | None = None
    resource_egrip: str | None = None
    resource_email: str | None = None
    resource_phone: str | None = None
    admin_tg_id: int | None = None


class _FakeBotProvider:
    def get_bot(self):  # pragma: no cover
        raise AssertionError("Not needed for build_bot_info_message()")


def test_build_bot_info_message_includes_configured_fields() -> None:
    # given
    settings = _FakeSettings(
        resource_inn="123456789012",
        resource_status="ИП",
        resource_email="support@example.com",
        resource_phone="+7 (999) 123-45-67",
    )
    ui = MenuUIService(bot_provider=_FakeBotProvider(), settings=settings)  # type: ignore[arg-type]

    # when
    text = ui.build_bot_info_message()

    # then
    assert "Информация о боте" in text
    assert "123456789012" in text
    assert "ИП" in text
    assert "support@example.com" in text
    assert "+7 (999) 123-45-67" in text


def test_build_bot_info_message_returns_empty_message_when_no_fields() -> None:
    # given
    ui = MenuUIService(bot_provider=_FakeBotProvider(), settings=_FakeSettings())  # type: ignore[arg-type]

    # when
    text = ui.build_bot_info_message()

    # then
    # Contract: if nothing is configured in env -> show a dedicated empty-state message.
    assert isinstance(text, str)
    assert text.strip() != ""

