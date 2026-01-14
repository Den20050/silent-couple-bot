"""Use case for changing partner nickname."""

import re

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.ui.settings_ui import SettingsUIService
from src.bot.handlers.settings.validators import (
    validate_user_exists,
    validate_subscription_active,
    validate_pair_access,
)

logger = get_logger(__name__)

# Nickname validation regex: only letters, numbers, and spaces
NICKNAME_PATTERN = re.compile(r'^[a-zA-Zа-яА-ЯёЁ0-9\s]+$')


def validate_nickname(nickname: str) -> bool:
    """Validate nickname format.
    
    Args:
        nickname: Nickname to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not nickname or len(nickname.strip()) == 0:
        return False
    
    if len(nickname) > 50:
        return False
    
    return bool(NICKNAME_PATTERN.match(nickname))


async def show_partner_selection(
    tg_id: int,
    session: AsyncSession,
    settings_ui: SettingsUIService,
    subscription_status_service,
) -> tuple[bool, str, dict | None]:
    """Show partner selection screen for nickname change.
    
    Args:
        tg_id: Telegram user ID
        session: Database session
        
    Returns:
        Tuple of (success: bool, message_text: str, reply_markup: dict | None)
    """
    try:
        pairs_repo = PairsRepository(session)
        all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
        
        if not all_pairs:
            return False, get_message("SETTINGS_NO_PAIR"), None
        
        # Validate user exists
        is_valid, user, error_msg = await validate_user_exists(session, tg_id, "SETTINGS_NO_PAIR")
        if not is_valid:
            return False, error_msg, None
        
        # If user has multiple pairs, show partner selection
        if len(all_pairs) > 1:
            text = "Выберите партнёра, для которого хотите изменить имя:"
            keyboard = settings_ui.build_partner_selection_keyboard(all_pairs, user.id, pairs_repo)
            return True, text, keyboard.model_dump()
        
        # Single pair - proceed directly to nickname input
        pair = all_pairs[0]
        
        # Validate subscription is active
        is_valid, error_msg, reply_markup = await validate_subscription_active(
            session, pair, show_pay_button=True
        )
        if not is_valid:
            return False, error_msg, reply_markup
        
        # Check if subscription is active
        if not await subscription_status_service.is_subscription_active(pair):
            return False, "Подписка неактивна", None
        
        # Get current nickname
        current_nickname = pairs_repo.get_my_nickname_for_partner(pair, user.id)
        
        # Prompt for nickname
        text = get_message("SETTINGS_NICKNAME_PROMPT")
        if current_nickname:
            text += f"\n\nТекущее имя (которое вы дали партнёру): <b>{current_nickname}</b>\nОтправьте новое имя или /clear для удаления."
        else:
            text += "\n\nОтправьте /clear для удаления имени (если оно было установлено ранее)."
        
        from src.services.messaging.templates import KeyboardTemplates
        keyboard = KeyboardTemplates.cancel_only("settings_back")
        
        return True, text, keyboard.model_dump()
    except Exception as e:
        logger.error(
            "Error in show_partner_selection",
            tg_id=tg_id,
            error=str(e),
            exc_info=True,
        )
        return False, get_message("SETTINGS_ERROR"), None


async def show_nickname_input_for_pair(
    tg_id: int,
    pair_id: int,
    session: AsyncSession,
    settings_ui: SettingsUIService,
    subscription_status_service,
) -> tuple[bool, str, dict | None]:
    """Show nickname input prompt for specific pair.
    
    Args:
        tg_id: Telegram user ID
        pair_id: Pair ID
        session: Database session
        
    Returns:
        Tuple of (success: bool, message_text: str, reply_markup: dict | None)
    """
    try:
        pairs_repo = PairsRepository(session)
        pair = await pairs_repo.get_by_id(pair_id)
        
        if not pair:
            return False, get_message("SETTINGS_NO_PAIR"), None
        
        # Validate user exists and has access to pair
        is_valid, user, error_msg = await validate_user_exists(session, tg_id, "SETTINGS_NO_PAIR")
        if not is_valid:
            return False, error_msg, None
        
        is_valid, error_msg = await validate_pair_access(session, pair, user.id, tg_id)
        if not is_valid:
            return False, error_msg, None
        
        # Validate subscription is active
        is_valid, error_msg, reply_markup = await validate_subscription_active(
            session, pair, show_pay_button=True
        )
        if not is_valid:
            return False, error_msg, reply_markup
        
        # Check if subscription is active
        if not await subscription_status_service.is_subscription_active(pair):
            return False, "Подписка неактивна", None
        
        # Get current nickname
        current_nickname = pairs_repo.get_my_nickname_for_partner(pair, user.id)
        
        # Prompt for nickname
        text = get_message("SETTINGS_NICKNAME_PROMPT")
        if current_nickname:
            text += f"\n\nТекущее имя (которое вы дали партнёру): <b>{current_nickname}</b>\nОтправьте новое имя или /clear для удаления."
        else:
            text += "\n\nОтправьте /clear для удаления имени (если оно было установлено ранее)."
        
        from src.services.messaging.templates import KeyboardTemplates
        keyboard = KeyboardTemplates.cancel_only("settings_back")
        
        return True, text, keyboard.model_dump()
    except Exception as e:
        logger.error(
            "Error in show_nickname_input_for_pair",
            tg_id=tg_id,
            pair_id=pair_id,
            error=str(e),
            exc_info=True,
        )
        return False, get_message("SETTINGS_ERROR"), None


async def update_nickname(
    tg_id: int,
    pair_id: int,
    user_id: int,
    nickname: str | None,
    session: AsyncSession,
) -> tuple[bool, str]:
    """Update partner nickname.
    
    Args:
        tg_id: Telegram user ID
        pair_id: Pair ID
        user_id: User ID
        nickname: New nickname (None to clear)
        session: Database session
        
    Returns:
        Tuple of (success: bool, message_text: str)
    """
    try:
        pairs_repo = PairsRepository(session)
        pair = await pairs_repo.get_by_id(pair_id)
        
        if not pair:
            return False, get_message("SETTINGS_NO_PAIR")
        
        # Verify user is part of this pair
        if pair.uid_a != user_id and pair.uid_b != user_id:
            return False, get_message("SETTINGS_NO_PAIR")
        
        # Update nickname
        if nickname is None:
            # Clear nickname
            await pairs_repo.clear_nickname(pair_id, user_id)
        else:
            # Validate nickname
            if not validate_nickname(nickname):
                return False, "❌ Некорректное имя. Используйте только буквы, цифры и пробелы."
            
            # Set nickname
            await pairs_repo.set_nickname(pair_id, user_id, nickname.strip())
        
        await session.commit()
        
        # Get updated nickname for confirmation
        updated_pair = await pairs_repo.get_by_id(pair_id)
        if not updated_pair:
            return False, get_message("SETTINGS_ERROR")
        
        updated_nickname = pairs_repo.get_my_nickname_for_partner(updated_pair, user_id)
        nickname_text = updated_nickname if updated_nickname else "не установлено"
        
        # Get mode text
        mode_text = (
            get_message("SETTINGS_MODE_CHAT")
            if updated_pair.mode == "chat"
            else get_message("SETTINGS_MODE_SILENT")
        )
        
        text = (
            f"{get_message('SETTINGS_TITLE')}\n\n"
            f"{get_message('SETTINGS_CURRENT_MODE', mode_text=mode_text)}\n"
            f"{get_message('SETTINGS_CURRENT_NICKNAME', nickname=nickname_text)}"
        )
        
        logger.info(
            "Nickname updated",
            tg_id=tg_id,
            pair_id=pair_id,
            user_id=user_id,
            nickname=nickname,
        )
        
        return True, text
    except Exception as e:
        logger.error(
            "Error in update_nickname",
            tg_id=tg_id,
            pair_id=pair_id,
            user_id=user_id,
            nickname=nickname,
            error=str(e),
            exc_info=True,
        )
        await session.rollback()
        return False, get_message("SETTINGS_ERROR")

