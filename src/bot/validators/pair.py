"""Pair validation utilities."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.exceptions import PairAccessDeniedError, PairNotFoundError
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.models import Pair
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository

logger = get_logger(__name__)


async def validate_pair_exists(
    session: AsyncSession,
    pair_id: int,
    error_message_key: str = "SETTINGS_NO_PAIR",
) -> Pair:
    """Validate pair exists.
    
    Args:
        session: Database session
        pair_id: Pair ID
        error_message_key: Message key for error (default: "SETTINGS_NO_PAIR")
        
    Returns:
        Pair object if found
        
    Raises:
        PairNotFoundError: If pair is not found
    """
    pairs_repo = PairsRepository(session)
    pair = await pairs_repo.get_by_id(pair_id)
    
    if not pair:
        logger.warning(
            "Pair not found",
            pair_id=pair_id,
        )
        raise PairNotFoundError(
            pair_id=pair_id,
            message_key=error_message_key,
            message=get_message(error_message_key),
        )
    
    return pair


async def validate_user_has_pair(
    session: AsyncSession,
    tg_id: int,
    error_message_key: str = "MENU_NO_PAIR_ALERT",
) -> Pair:
    """Validate user has at least one pair.
    
    Args:
        session: Database session
        tg_id: Telegram user ID
        error_message_key: Message key for error (default: "MENU_NO_PAIR_ALERT")
        
    Returns:
        Pair object if user has pair
        
    Raises:
        PairNotFoundError: If user has no pair
    """
    pairs_repo = PairsRepository(session)
    pair = await pairs_repo.get_by_user_tg_id(tg_id)
    
    if not pair:
        logger.warning(
            "User has no pair",
            tg_id=tg_id,
        )
        raise PairNotFoundError(
            tg_id=tg_id,
            message_key=error_message_key,
            message=get_message(error_message_key),
        )
    
    return pair


async def validate_pair_access(
    session: AsyncSession,
    pair: Pair,
    user_id: int,
    tg_id: int,
    error_message_key: str = "SETTINGS_NO_PAIR",
) -> None:
    """Validate user has access to pair.
    
    Args:
        session: Database session
        pair: Pair object
        user_id: User ID
        tg_id: Telegram user ID (for verification)
        error_message_key: Message key for error (default: "SETTINGS_NO_PAIR")
        
    Raises:
        PairAccessDeniedError: If user doesn't have access to pair
    """
    # Verify user is part of this pair
    if pair.uid_a != user_id and pair.uid_b != user_id:
        logger.warning(
            "User does not have access to pair",
            user_id=user_id,
            tg_id=tg_id,
            pair_id=pair.id,
        )
        raise PairAccessDeniedError(
            user_id=user_id,
            pair_id=pair.id,
            message_key=error_message_key,
            message=get_message(error_message_key),
        )
    
    # Verify tg_id matches user_id
    users_repo = UsersRepository(session)
    user = await users_repo.get_by_id(user_id)
    if not user or user.tg_id != tg_id:
        logger.warning(
            "User ID mismatch",
            user_id=user_id,
            tg_id=tg_id,
            pair_id=pair.id,
        )
        raise PairAccessDeniedError(
            user_id=user_id,
            pair_id=pair.id,
            message_key=error_message_key,
            message=get_message(error_message_key),
        )


async def validate_user_has_any_pair(
    session: AsyncSession,
    tg_id: int,
    error_message_key: str = "SETTINGS_NO_PAIR",
) -> list:
    """Validate user has at least one pair and return all pairs.
    
    Args:
        session: Database session
        tg_id: Telegram user ID
        error_message_key: Message key for error (default: "SETTINGS_NO_PAIR")
        
    Returns:
        List of Pair objects
        
    Raises:
        PairNotFoundError: If user has no pairs
    """
    pairs_repo = PairsRepository(session)
    all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    
    if not all_pairs:
        logger.warning(
            "User has no pairs",
            tg_id=tg_id,
        )
        raise PairNotFoundError(
            tg_id=tg_id,
            message_key=error_message_key,
            message=get_message(error_message_key),
        )
    
    return all_pairs

