from __future__ import annotations

from src.worker.tasks.nudges import build_share_nudge_key, get_share_nudge_ttl_seconds


def test_build_share_nudge_key_is_stable_and_has_no_date() -> None:
    key = build_share_nudge_key(123)
    assert key == "share_nudge_sent:user:123"
    assert "-" not in key  # crude guard: no YYYY-MM-DD fragments


def test_get_share_nudge_ttl_seconds_5_days() -> None:
    assert get_share_nudge_ttl_seconds(120) == 120 * 3600

