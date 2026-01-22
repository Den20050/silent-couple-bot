"""Use case for sending wishes to partners."""

from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.services.messaging.wish_sender import WishSenderService
from src.services.telegram.messenger import TelegramMessenger

logger = get_logger(__name__)


async def send_wish_to_partner(
    session: AsyncSession,
    pair,
    user_id: int,
    tg_id: int,
    pic_type: str,
    today: date,
    telegram_messenger: TelegramMessenger,
    redis=None,
) -> tuple[bool, Optional[str]]:
    """Send wish to a single partner.
    
    Args:
        session: Database session
        pair: Pair object
        user_id: User ID of the sender
        tg_id: Telegram ID of the sender
        pic_type: Picture type ("morning" or "evening")
        today: Current date
        telegram_messenger: Telegram messenger instance
        
    Returns:
        Tuple of (success: bool, partner_nickname: Optional[str])
    """
    wish_sender = WishSenderService(session, telegram_messenger, redis=redis)
    return await wish_sender.send_wish_to_partner(
        pair=pair,
        user_id=user_id,
        tg_id=tg_id,
        pic_type=pic_type,
        today=today,
    )


async def send_wish_to_all_partners(
    session: AsyncSession,
    active_pairs: list,
    user_id: int,
    tg_id: int,
    pic_type: str,
    today: date,
    telegram_messenger: TelegramMessenger,
) -> tuple[int, list[str]]:
    """Send wish to all active partners.
    
    Args:
        session: Database session
        active_pairs: List of active pairs
        user_id: User ID of the sender
        tg_id: Telegram ID of the sender
        pic_type: Picture type ("morning" or "evening")
        today: Current date
        telegram_messenger: Telegram messenger instance
        
    Returns:
        Tuple of (sent_count: int, partner_nicknames: list[str])
    """
    wish_sender = WishSenderService(session, telegram_messenger)
    return await wish_sender.send_wish_to_all_partners(
        active_pairs=active_pairs,
        user_id=user_id,
        tg_id=tg_id,
        pic_type=pic_type,
        today=today,
    )

