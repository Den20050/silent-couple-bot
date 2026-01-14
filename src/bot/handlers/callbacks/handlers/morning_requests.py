"""Morning request handlers."""

from datetime import date

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus
from src.core.messages import get_message
from src.core.logger import get_logger
from src.core.config import Settings
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.users import UsersRepository
from src.services.telegram.messenger import TelegramMessenger
from src.bot.handlers.callbacks.validators import (
    parse_callback_data,
    validate_pair_and_user,
    validate_user_has_active_pairs,
)
from src.bot.handlers.callbacks.use_cases.send_wish import (
    send_wish_to_partner,
    send_wish_to_all_partners,
)
from src.bot.handlers.callbacks.use_cases.schedule_reminders import (
    schedule_reminder_tasks,
)
from src.bot.handlers.callbacks.formatters import format_confirmation_message

logger = get_logger(__name__)

router = Router(name="morning_requests")


@router.callback_query(F.data.startswith("request_morning_all_"))
async def handle_request_morning_all(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle morning request button for all partners (user with multiple pairs)."""
    # Parse callback data: request_morning_all_{user_id}
    parsed = parse_callback_data(callback.data, expected_parts=4, prefix="request_morning_all_")
    if not parsed:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    user_id = parsed[0]
    tg_id = callback.from_user.id
    
    logger.info(
        "Processing request_morning_all callback",
        user_id=user_id,
        tg_id=tg_id,
        callback_data=callback.data,
    )
    
    # Validate user
    users_repo = UsersRepository(session)
    user = await users_repo.get_by_id(user_id)
    if not user or user.tg_id != tg_id:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    # Validate user has active pairs
    active_pairs = await validate_user_has_active_pairs(session, tg_id)
    if not active_pairs:
        await callback.answer("❌ У вас нет активных пар", show_alert=True)
        return
    
    # Send wish to all partners
    today = date.today()
    sent_count, partner_nicknames = await send_wish_to_all_partners(
        session=session,
        active_pairs=active_pairs,
        user_id=user_id,
        tg_id=tg_id,
        pic_type="morning",
        today=today,
        telegram_messenger=telegram_messenger,
    )
    
    # Edit message to show success with partner nicknames
    if sent_count > 0:
        message_text = format_confirmation_message(partner_nicknames)
        await telegram_messenger.edit_message(
            chat_id=tg_id,
            message_id=callback.message.message_id,
            text=message_text,
        )
        await callback.answer()
    else:
        await callback.answer("❌ Не удалось отправить пожелания", show_alert=True)


@router.callback_query(F.data.startswith("request_morning_"))
async def handle_request_morning(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
    settings: Settings,
) -> None:
    """Handle morning request button."""
    # Parse callback data: request_morning_{pair_id}_{user_id}
    parsed = parse_callback_data(callback.data, expected_parts=4, prefix="request_morning_")
    if not parsed:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    pair_id, user_id = parsed
    tg_id = callback.from_user.id
    
    logger.info(
        "Processing request_morning callback",
        pair_id=pair_id,
        user_id=user_id,
        tg_id=tg_id,
        callback_data=callback.data,
    )
    
    # Validate pair and user
    validation_result = await validate_pair_and_user(
        session, pair_id, user_id, tg_id
    )
    if not validation_result:
        await callback.answer(get_message("CALLBACK_PAIR_NOT_FOUND"), show_alert=True)
        return
    
    pair, user_a, user_b, user = validation_result
    
    # Check if subscription is past due
    if pair.status == PairStatus.PAST_DUE.value:
        await callback.answer(
            get_message("WORKER_PAST_DUE_DUNNING"),
            show_alert=True
        )
        return
    
    today = date.today()
    daily_state_repo = DailyStateRepository(session)
    
    # Send wish to partner
    success, partner_nickname = await send_wish_to_partner(
        session=session,
        pair=pair,
        user_id=user_id,
        tg_id=tg_id,
        pic_type="morning",
        today=today,
        telegram_messenger=telegram_messenger,
    )
    
    if not success:
        # Check if partner already sent
        daily_state = await daily_state_repo.get_by_pair_and_day(pair_id, today)
        if daily_state and daily_state.morning_initiator is not None:
            await callback.answer(
                get_message("CALLBACK_PARTNER_ALREADY_SENT"),
                show_alert=True
            )
        else:
            await callback.answer(
                get_message("CALLBACK_NO_IMAGES_AVAILABLE"),
                show_alert=True
            )
        return
    
    # Success - edit message
    await telegram_messenger.edit_message(
        chat_id=tg_id,
        message_id=callback.message.message_id,
        text="✅ Вы отправили пожелание",
    )
    
    # Schedule reminder tasks
    partner_tg_id = user_b.tg_id if user_a.tg_id == tg_id else user_a.tg_id
    recipient_user = user_b if user_a.id == user_id else user_a
    
    await schedule_reminder_tasks(
        pair_id=pair_id,
        initiator_tg_id=tg_id,
        recipient_tg_id=partner_tg_id,
        recipient_user_id=recipient_user.id,
        pic_type="morning",
        settings=settings,
    )
    
    await callback.answer()

