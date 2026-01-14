"""Use case for responding to wishes."""

from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.services.messaging.response_sender import ResponseSenderService
from src.services.telegram.messenger import TelegramMessenger

logger = get_logger(__name__)


async def respond_to_wish(
    session: AsyncSession,
    pair_id: int,
    check_day: date,
    tg_id: int,
    initiator_tg_id: int,
    pic_type: str,
    telegram_messenger: TelegramMessenger,
) -> tuple[bool, Optional[str]]:
    """Respond to a wish from partner.
    
    Args:
        session: Database session
        pair_id: Pair ID
        check_day: Day to check (for reminders, might be previous day)
        tg_id: Telegram ID of the responder
        initiator_tg_id: Telegram ID of the initiator (from callback_data)
        pic_type: Picture type ("morning" or "evening")
        telegram_messenger: Telegram messenger instance
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        error_message is None on success, otherwise contains error key
    """
    response_sender = ResponseSenderService(session, telegram_messenger)
    return await response_sender.send_response(
        pair_id=pair_id,
        check_day=check_day,
        tg_id=tg_id,
        initiator_tg_id=initiator_tg_id,
        pic_type=pic_type,
    )

