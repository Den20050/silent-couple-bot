"""User validation utilities."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.exceptions import UserNotFoundError
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.models import User
from src.db.repositories.users import UsersRepository

logger = get_logger(__name__)


async def validate_user_exists(
    session: AsyncSession,
    tg_id: int,
    error_message_key: str = "MENU_USER_NOT_FOUND",
) -> User:
    """Validate user exists.
    
    Args:
        session: Database session
        tg_id: Telegram user ID
        error_message_key: Message key for error (default: "MENU_USER_NOT_FOUND")
        
    Returns:
        User object if found
        
    Raises:
        UserNotFoundError: If user is not found
    """
    users_repo = UsersRepository(session)
    user = await users_repo.get_by_tg_id(tg_id)
    
    if not user:
        logger.warning(
            "User not found",
            tg_id=tg_id,
        )
        raise UserNotFoundError(
            tg_id=tg_id,
            message_key=error_message_key,
            message=get_message(error_message_key),
        )
    
    return user

