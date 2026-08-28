from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.timezone import (
    get_effective_utc_offset,
    normalize_timezone_name,
    sync_user_timezone,
)


def test_normalize_timezone_name_accepts_iana() -> None:
    assert normalize_timezone_name("Europe/Moscow") == "Europe/Moscow"


def test_normalize_timezone_name_rejects_invalid() -> None:
    assert normalize_timezone_name("Not/AZone") is None


def test_get_effective_utc_offset_prefers_timezone_name() -> None:
    user = SimpleNamespace(timezone_name="Europe/Moscow", utc_offset=0)
    assert get_effective_utc_offset(user) == 3


def test_get_effective_utc_offset_falls_back_to_stored_offset() -> None:
    user = SimpleNamespace(timezone_name=None, utc_offset=5)
    assert get_effective_utc_offset(user) == 5


@pytest.mark.asyncio
async def test_sync_user_timezone_updates_user() -> None:
    user = SimpleNamespace(
        tg_id=100,
        timezone_name=None,
        utc_offset=3,
    )
    session = MagicMock()
    repo = SimpleNamespace(
        get_by_tg_id=AsyncMock(return_value=user),
        update_timezone=AsyncMock(return_value=user),
    )

    import src.services.timezone as tz_module

    original_repo = tz_module.UsersRepository
    tz_module.UsersRepository = MagicMock(return_value=repo)
    try:
        ok = await sync_user_timezone(
            session,
            100,
            timezone_name="Asia/Vladivostok",
            utc_offset=10,
        )
    finally:
        tz_module.UsersRepository = original_repo

    assert ok is True
    repo.update_timezone.assert_awaited_once()
    session.commit.assert_awaited_once()
