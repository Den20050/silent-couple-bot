from __future__ import annotations

import pytest

from src.worker.services.notification_builder import NotificationBuilder


@pytest.mark.asyncio
async def test_week_summary_silent_with_nickname() -> None:
    builder = NotificationBuilder(messenger=None)  # type: ignore[arg-type]
    text = await builder.build_week_summary_message(
        pair_mode="silent",
        days_count=4,
        partner_nickname="Мама",
    )
    assert text.startswith("Вы с Мама уже 4 дней")


@pytest.mark.asyncio
async def test_week_summary_silent_without_nickname() -> None:
    builder = NotificationBuilder(messenger=None)  # type: ignore[arg-type]
    text = await builder.build_week_summary_message(pair_mode="silent", days_count=4)
    assert text.startswith("Вы уже 4 дней")

