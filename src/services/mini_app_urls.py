"""Helpers for building Telegram Mini App URLs."""

from __future__ import annotations

from urllib.parse import urlencode

from src.core.config import settings


def build_tz_sync_url(**params: str | int) -> str:
    """Build URL for the timezone sync Mini App page."""
    base = settings.mini_app_url.rstrip("/")
    clean = {k: str(v) for k, v in params.items() if v is not None}
    query = urlencode(clean)
    return f"{base}/tz-sync?{query}" if query else f"{base}/tz-sync"
