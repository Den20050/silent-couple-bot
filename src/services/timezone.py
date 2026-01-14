"""Timezone detection service."""

import httpx
from typing import Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


async def detect_timezone_from_ip(ip: Optional[str]) -> Optional[int]:
    """Detect timezone (UTC offset) from IP address.

    Args:
        ip: IP address string (e.g., "192.168.1.1")

    Returns:
        UTC offset in hours (e.g., 3 for UTC+3) or None if detection failed
    """
    if not ip or ip == "0.0.0.0" or ip.startswith("127."):
        return None

    try:
        # Use free ip-api.com service
        # (no API key required, rate limit: 45 requests/minute)
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"http://ip-api.com/json/{ip}?fields=timezone"
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                timezone_str = data.get("timezone")

                if timezone_str:
                    # Convert timezone string to UTC offset
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


def _timezone_to_offset(timezone_str: str) -> Optional[int]:
    """Convert timezone string to UTC offset using pytz.

    Args:
        timezone_str: Timezone string
            (e.g., "Europe/Moscow", "America/New_York")

    Returns:
        UTC offset in hours (e.g., 3 for UTC+3)
        or None if conversion failed
    """
    try:
        import pytz
        from datetime import datetime

        # Get timezone object
        tz = pytz.timezone(timezone_str)

        # Get current UTC offset (accounts for DST)
        now = datetime.now(tz)
        offset = now.utcoffset()

        # Convert timedelta to hours
        if offset:
            total_seconds = offset.total_seconds()
            hours = int(total_seconds / 3600)
            return hours

    except Exception as e:
        logger.warning(
            "Failed to convert timezone to offset",
            timezone=timezone_str,
            error=str(e),
        )

    return None
