"""Timezone detection and sync service."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.db.repositories.users import UsersRepository

logger = get_logger(__name__)


async def detect_timezone_from_ip(ip: Optional[str]) -> Optional[int]:
    """Detect timezone (UTC offset) from IP address."""
    if not ip or ip == "0.0.0.0" or ip.startswith("127."):
        return None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"http://ip-api.com/json/{ip}?fields=timezone"
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                timezone_str = data.get("timezone")

                if timezone_str:
                    utc_offset = _timezone_to_offset(timezone_str)
                    if utc_offset is not None:
                        logger.info(
                            "Timezone detected from IP",
                            ip=ip,
                            timezone=timezone_str,
                            utc_offset=utc_offset,
                        )
                        return utc_offset

    except Exception as e:
        logger.warning(
            "Failed to detect timezone from IP",
            ip=ip,
            error=str(e),
        )

    return None


def _timezone_to_offset(timezone_str: str, at_time: datetime | None = None) -> Optional[int]:
    """Convert IANA timezone string to UTC offset in hours."""
    try:
        import pytz

        tz = pytz.timezone(timezone_str)
        now = at_time or datetime.utcnow()
        localized = pytz.utc.localize(now).astimezone(tz)
        offset = localized.utcoffset()
        if offset is not None:
            return int(offset.total_seconds() / 3600)
    except Exception as e:
        logger.warning(
            "Failed to convert timezone to offset",
            timezone=timezone_str,
            error=str(e),
        )

    return None


def normalize_timezone_name(timezone_name: str | None) -> str | None:
    """Validate and normalize an IANA timezone name."""
    if not timezone_name:
        return None
    try:
        import pytz

        pytz.timezone(timezone_name)
        return timezone_name
    except Exception:
        logger.warning("Invalid timezone name rejected", timezone_name=timezone_name)
        return None


def is_timezone_configured(user_obj: Any) -> bool:
    """True when the user's timezone was synced from the phone Mini App."""
    return bool(getattr(user_obj, "timezone_name", None))


def format_timezone_label(user_obj: Any) -> str:
    """Human-readable timezone for confirmation messages."""
    name = getattr(user_obj, "timezone_name", None) or "—"
    offset = get_effective_utc_offset(user_obj) if is_timezone_configured(user_obj) else None
    if offset is None:
        return str(name)
    sign = "+" if offset >= 0 else ""
    return f"{name}, UTC{sign}{offset}"


def get_effective_utc_offset(user_obj: Any, now_utc: datetime | None = None) -> int:
    """Return the user's UTC offset, preferring stored IANA timezone when available."""
    if not is_timezone_configured(user_obj):
        return 0
    timezone_name = getattr(user_obj, "timezone_name", None)
    if timezone_name:
        offset = _timezone_to_offset(timezone_name, now_utc)
        if offset is not None:
            return offset
    stored = getattr(user_obj, "utc_offset", None)
    if stored is not None:
        return int(stored)
    return 0


async def sync_user_timezone(
    session: AsyncSession,
    tg_id: int,
    *,
    timezone_name: str | None,
    utc_offset: int,
) -> bool:
    """Persist timezone from Mini App (phone system settings).

    Returns True when the timezone was updated or unchanged, False on validation failure.
    """
    normalized_name = normalize_timezone_name(timezone_name)
    if normalized_name:
        computed_offset = _timezone_to_offset(normalized_name)
        if computed_offset is not None:
            utc_offset = computed_offset
    elif utc_offset < -12 or utc_offset > 14:
        logger.warning("Invalid utc_offset rejected", tg_id=tg_id, utc_offset=utc_offset)
        return False

    users_repo = UsersRepository(session)
    user = await users_repo.get_by_tg_id(tg_id)
    if not user:
        logger.warning("Timezone sync: user not found", tg_id=tg_id)
        return False

    if user.timezone_name == normalized_name and user.utc_offset == utc_offset:
        return True

    await users_repo.update_timezone(
        tg_id,
        utc_offset=utc_offset,
        timezone_name=normalized_name,
    )
    await session.commit()
    logger.info(
        "User timezone synced from Mini App",
        tg_id=tg_id,
        timezone_name=normalized_name,
        utc_offset=utc_offset,
    )
    return True
