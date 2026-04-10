"""Factory for creating Bot instances with optional proxy support."""

from typing import Optional

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from src.core.logger import get_logger

logger = get_logger(__name__)


def create_bot(token: str, proxy_url: Optional[str] = None) -> Bot:
    """Create a Bot instance, optionally routing through a proxy.

    Supports:
    - HTTP proxy:   ``http://host:port``
    - SOCKS5 proxy: ``socks5://user:pass@host:port``  (requires ``aiohttp-socks``)

    Args:
        token: Telegram bot token.
        proxy_url: Optional proxy URL. If None, connects to Telegram directly.

    Returns:
        Configured Bot instance.
    """
    default_props = DefaultBotProperties(parse_mode=ParseMode.HTML)

    if proxy_url:
        logger.info("Creating Bot with proxy", proxy=_mask_proxy(proxy_url))
        session = AiohttpSession(proxy=proxy_url)
        return Bot(token=token, session=session, default=default_props)

    return Bot(token=token, default=default_props)


def _mask_proxy(proxy_url: str) -> str:
    """Return proxy URL with credentials hidden for safe logging."""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(proxy_url)
        if parsed.password:
            masked = parsed._replace(netloc=f"{parsed.hostname}:{parsed.port}")
            return urlunparse(masked)
    except Exception:
        pass
    return proxy_url
