"""Response handlers (tap_morning, tap_evening)."""

from datetime import date

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.messages import get_message
from src.core.logger import get_logger
from src.core.di.container import Container
from src.services.telegram.messenger import TelegramMessenger
from src.bot.handlers.callbacks.validators import parse_callback_data_with_day
from src.bot.handlers.callbacks.use_cases.respond_to_wish import respond_to_wish
from src.services.messaging.active_action_message import is_message_active, ActionKind

logger = get_logger(__name__)

router = Router(name="responses")


@router.callback_query(F.data.startswith("tap_morning_"))
async def handle_tap_morning(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
    container: Container,
) -> None:
    """Handle morning tap (response)."""
    tg_id = callback.from_user.id
    if callback.message:
        ok = await is_message_active(
            redis=container.redis,
            tg_id=tg_id,
            message_id=callback.message.message_id,
            kind=ActionKind.REMINDER,
        )
        if not ok:
            # Best-effort: remove stale buttons so the user stops clicking.
            await telegram_messenger.remove_reply_markup(
                chat_id=tg_id,
                message_id=callback.message.message_id,
            )
            await callback.answer(get_message("CALLBACK_STALE_MESSAGE"), show_alert=True)
            return

    # Parse callback data: tap_morning_{pair_id}_{initiator_tg_id}|{day_iso}
    parsed = parse_callback_data_with_day(callback.data, prefix="tap_morning_")
    if not parsed:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    pair_id, initiator_tg_id, day_iso = parsed
    
    # Determine which day to check
    check_day = date.fromisoformat(day_iso) if day_iso else date.today()
    
    logger.info(
        "Processing tap_morning callback",
        pair_id=pair_id,
        initiator_tg_id=initiator_tg_id,
        tg_id=tg_id,
        check_day=str(check_day),
        callback_data=callback.data,
    )
    
    # Respond to wish
    success, error_key = await respond_to_wish(
        session=session,
        pair_id=pair_id,
        check_day=check_day,
        tg_id=tg_id,
        initiator_tg_id=initiator_tg_id,
        pic_type="morning",
        telegram_messenger=telegram_messenger,
    )
    
    if not success:
        await callback.answer(get_message(error_key or "CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    # Remove button from the message
    await telegram_messenger.remove_reply_markup(
        chat_id=tg_id,
        message_id=callback.message.message_id,
    )
    
    # Send confirmation message
    await telegram_messenger.send_message(
        chat_id=tg_id,
        text=get_message("CALLBACK_WISH_RESPONDED"),
    )
    
    await callback.answer(get_message("CALLBACK_RESPONSE_SENT"))


@router.callback_query(F.data.startswith("tap_evening_"))
async def handle_tap_evening(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
    container: Container,
) -> None:
    """Handle evening tap (response)."""
    tg_id = callback.from_user.id
    if callback.message:
        ok = await is_message_active(
            redis=container.redis,
            tg_id=tg_id,
            message_id=callback.message.message_id,
            kind=ActionKind.REMINDER,
        )
        if not ok:
            await telegram_messenger.remove_reply_markup(
                chat_id=tg_id,
                message_id=callback.message.message_id,
            )
            await callback.answer(get_message("CALLBACK_STALE_MESSAGE"), show_alert=True)
            return

    # Parse callback data: tap_evening_{pair_id}_{initiator_tg_id}|{day_iso}
    parsed = parse_callback_data_with_day(callback.data, prefix="tap_evening_")
    if not parsed:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    pair_id, initiator_tg_id, day_iso = parsed
    
    # Determine which day to check
    check_day = date.fromisoformat(day_iso) if day_iso else date.today()
    
    logger.info(
        "Processing tap_evening callback",
        pair_id=pair_id,
        initiator_tg_id=initiator_tg_id,
        tg_id=tg_id,
        check_day=str(check_day),
        callback_data=callback.data,
    )
    
    # Respond to wish
    success, error_key = await respond_to_wish(
        session=session,
        pair_id=pair_id,
        check_day=check_day,
        tg_id=tg_id,
        initiator_tg_id=initiator_tg_id,
        pic_type="evening",
        telegram_messenger=telegram_messenger,
    )
    
    if not success:
        await callback.answer(get_message(error_key or "CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    # Remove button from the message
    await telegram_messenger.remove_reply_markup(
        chat_id=tg_id,
        message_id=callback.message.message_id,
    )
    
    # Send confirmation message
    await telegram_messenger.send_message(
        chat_id=tg_id,
        text=get_message("CALLBACK_WISH_RESPONDED"),
    )
    
    await callback.answer(get_message("CALLBACK_RESPONSE_SENT"))

