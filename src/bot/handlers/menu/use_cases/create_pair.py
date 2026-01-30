"""Use case for creating pair."""

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.telegram.bot_provider import BotProvider

logger = get_logger(__name__)


async def handle_create_pair_command(
    message: Message,
    session: AsyncSession,
    bot_provider: BotProvider,  # noqa: ARG001
) -> tuple[bool, str, dict | None]:
    """Handle /create_pair command - show mode selection for creating new pair.
    
    Args:
        message: Message object
        session: Database session
        bot_provider: Bot provider instance (unused)
        
    Returns:
        Tuple of (success: bool, message_text: str, reply_markup: dict | None)
    """
    try:
        tg_id = message.from_user.id
        
        users_repo = UsersRepository(session)
        user = await users_repo.get_by_tg_id(tg_id)
        
        if not user:
            return False, get_message("MENU_USER_NOT_FOUND"), None
        
        # Check if user has consent (skip if user already has any pairs)
        pairs_repo = PairsRepository(session)
        user_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
        if not user.consent and not user_pairs:
            return False, (
                "Для создания пары необходимо принять пользовательское соглашение. "
                "Используйте команду /start"
            ), None
        
        # Always show mode selection (same as first time)
        from src.bot.handlers.start.ui.builders import get_mode_keyboard
        
        return True, get_message("START_MODE_SELECTION_PROMPT"), get_mode_keyboard().model_dump()
    except Exception as e:
        logger.error("Error in handle_create_pair_command", error=str(e), exc_info=True)
        return False, get_message("MENU_ERROR"), None

