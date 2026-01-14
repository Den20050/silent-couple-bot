"""Validation utilities for callback handlers."""

from typing import Optional

from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus
from src.core.messages import get_message
from src.core.logger import get_logger
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository

logger = get_logger(__name__)


def parse_callback_data(
    callback_data: str,
    expected_parts: int,
    prefix: str,
) -> Optional[tuple[int, ...]]:
    """Parse callback data and extract IDs.
    
    Args:
        callback_data: Callback data string
        expected_parts: Expected number of parts after prefix
        prefix: Expected prefix (e.g., "request_morning_")
        
    Returns:
        Tuple of parsed IDs or None if parsing failed
    """
    if not callback_data.startswith(prefix):
        return None
    
    parts = callback_data.split("_")
    if len(parts) < expected_parts:
        return None
    
    try:
        # Extract IDs (skip prefix parts)
        prefix_parts_count = len(prefix.rstrip("_").split("_"))
        ids = tuple(int(parts[i]) for i in range(prefix_parts_count, len(parts)))
        return ids
    except (ValueError, IndexError) as e:
        logger.error(
            "Failed to parse callback_data",
            callback_data=callback_data,
            prefix=prefix,
            error=str(e),
        )
        return None


def parse_callback_data_with_day(
    callback_data: str,
    prefix: str,
) -> Optional[tuple[int, int, Optional[str]]]:
    """Parse callback data with optional day ISO format.
    
    Args:
        callback_data: Callback data string (e.g., "tap_morning_{pair_id}_{initiator_tg_id}|{day_iso}")
        prefix: Expected prefix (e.g., "tap_morning_")
        
    Returns:
        Tuple of (pair_id, initiator_tg_id, day_iso) or None if parsing failed
    """
    if not callback_data.startswith(prefix):
        return None
    
    # Check if day is included (for reminders)
    # Format: tap_morning_{pair_id}_{initiator_tg_id}|{day_iso}
    day_iso = None
    if "|" in callback_data:
        try:
            from datetime import date as date_class
            # Split by "|" to get day part
            day_part = callback_data.split("|")[1]
            day_iso = day_part
            # Validate it's a valid date
            date_class.fromisoformat(day_iso)
        except (ValueError, IndexError) as e:
            logger.warning(
                "Failed to parse day from callback_data",
                callback_data=callback_data,
                error=str(e),
            )
            day_iso = None
    
    # Parse IDs from prefix part
    prefix_part = callback_data.split("|")[0]
    parts = prefix_part.split("_")
    prefix_parts_count = len(prefix.rstrip("_").split("_"))
    
    if len(parts) < prefix_parts_count + 2:
        return None
    
    try:
        pair_id = int(parts[prefix_parts_count])
        initiator_tg_id = int(parts[prefix_parts_count + 1])
        return (pair_id, initiator_tg_id, day_iso)
    except (ValueError, IndexError) as e:
        logger.error(
            "Failed to parse callback_data",
            callback_data=callback_data,
            prefix=prefix,
            error=str(e),
        )
        return None


async def validate_pair_and_user(
    session: AsyncSession,
    pair_id: int,
    user_id: int,
    tg_id: int,
) -> Optional[tuple]:
    """Validate pair and user exist and match.
    
    Args:
        session: Database session
        pair_id: Pair ID
        user_id: User ID
        tg_id: Telegram user ID
        
    Returns:
        Tuple of (pair, user_a, user_b) if valid, None otherwise
    """
    pairs_repo = PairsRepository(session)
    users_repo = UsersRepository(session)
    
    pair = await pairs_repo.get_by_id(pair_id)
    if not pair:
        logger.warning(
            "Pair not found",
            pair_id=pair_id,
            user_id=user_id,
            tg_id=tg_id,
        )
        return None
    
    # Check if subscription is past due
    if pair.status == PairStatus.PAST_DUE.value:
        return None
    
    # Get users
    user_a = await users_repo.get_by_id(pair.uid_a)
    user_b = await users_repo.get_by_id(pair.uid_b)
    if not user_a or not user_b:
        return None
    
    # Verify user matches
    user = await users_repo.get_by_id(user_id)
    if not user or user.tg_id != tg_id:
        return None
    
    return (pair, user_a, user_b, user)


async def validate_user_has_active_pairs(
    session: AsyncSession,
    tg_id: int,
) -> Optional[list]:
    """Validate user has active pairs.
    
    Args:
        session: Database session
        tg_id: Telegram user ID
        
    Returns:
        List of active pairs or None if validation failed
    """
    pairs_repo = PairsRepository(session)
    users_repo = UsersRepository(session)
    
    # Get user
    user = await users_repo.get_by_tg_id(tg_id)
    if not user:
        return None
    
    # Get all active pairs for this user
    all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    active_pairs = [
        p for p in all_pairs
        if p.status in (PairStatus.TRIAL.value, PairStatus.ACTIVE.value)
    ]
    
    if not active_pairs:
        return None
    
    return active_pairs

