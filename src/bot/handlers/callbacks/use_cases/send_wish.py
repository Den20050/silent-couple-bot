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
) -> tuple[bool, Optional[str], bool]:
    """Send wish to a single partner.

    Returns:
        (success, partner_nickname, delivered_immediately)
    """
    wish_sender = WishSenderService(session, telegram_messenger, redis=redis)
    return await wish_sender.send_wish_to_partner(
        pair=pair,
        user_id=user_id,
        tg_id=tg_id,
        pic_type=pic_type,
        today=today,
    )
