from types import SimpleNamespace

from src.services.messaging.ui.notification_window_ui import (
    notif_time_evening_prompt_text,
    notif_time_morning_prompt_text,
    partner_id_for_pair,
)


def test_partner_id_for_pair():
    pair = SimpleNamespace(uid_a=1, uid_b=2)
    assert partner_id_for_pair(pair, 1) == 2
    assert partner_id_for_pair(pair, 2) == 1


def test_morning_prompt_without_partner():
    user = SimpleNamespace(morning_window_start_hour=7, evening_window_start_hour=21)
    text = notif_time_morning_prompt_text(user)
    assert "07–08" in text
    assert "Сейчас установлено" in text
    assert "партнёра" not in text


def test_morning_prompt_with_partner():
    user = SimpleNamespace(morning_window_start_hour=8, evening_window_start_hour=21)
    partner = SimpleNamespace(morning_window_start_hour=7, evening_window_start_hour=20)
    text = notif_time_morning_prompt_text(user, partner)
    assert "08–09" in text
    assert "07–08" in text
    assert "партнёра" in text
    assert "часовых поясов" in text


def test_evening_prompt_with_partner():
    user = SimpleNamespace(morning_window_start_hour=7, evening_window_start_hour=22)
    partner = SimpleNamespace(morning_window_start_hour=6, evening_window_start_hour=21)
    text = notif_time_evening_prompt_text(user, partner)
    assert "22–23" in text
    assert "21–22" in text
