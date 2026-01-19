from src.services.messaging.partner_label import format_partner_label


def test_format_partner_label_prefers_nickname() -> None:
    assert (
        format_partner_label(partner_nickname="Мама", partner_username="someuser")
        == "Мама"
    )


def test_format_partner_label_username_with_at() -> None:
    assert (
        format_partner_label(partner_nickname=None, partner_username="@someuser")
        == "@someuser"
    )


def test_format_partner_label_username_without_at() -> None:
    assert (
        format_partner_label(partner_nickname=None, partner_username="someuser")
        == "@someuser"
    )


def test_format_partner_label_empty_returns_none() -> None:
    assert format_partner_label(partner_nickname=None, partner_username=None) is None
    assert format_partner_label(partner_nickname="   ", partner_username="   ") is None

