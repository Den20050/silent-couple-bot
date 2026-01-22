"""Evening request handlers."""

from datetime import date

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus
from src.core.messages import get_message
from src.core.logger import get_logger
from src.core.config import Settings
from src.db.repositories.daily_state import DailyStateRepository
from src.services.telegram.messenger import TelegramMessenger
from src.core.di.container import Container
from src.bot.handlers.callbacks.validators import (
    parse_callback_data,
    validate_pair_and_user,
)
from src.bot.handlers.callbacks.use_cases.send_wish import (
    send_wish_to_partner,
)
from src.bot.handlers.callbacks.use_cases.schedule_reminders import (
    schedule_reminder_tasks,
)
from src.services.messaging.ui.wish_request_ui import WishRequestUIService
from src.services.messaging.wish_request_prompt_refresher import refresh_aggregated_wish_prompt
from src.services.messaging.active_action_message import is_message_active, ActionKind

logger = get_logger(__name__)

router = Router(name="evening_requests")


@router.callback_query(F.data.startswith("request_evening_all_"))
async def handle_request_evening_all_legacy(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Legacy handler: 'send to all' is deprecated; convert prompt to per-partner UI."""
    parsed = parse_callback_data(
        callback.data, expected_parts=4, prefix="request_evening_all_"
    )
    if not parsed:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    (user_id,) = parsed
    tg_id = callback.from_user.id

    # Ensure the callback belongs to the same user (basic safety)
    from src.db.repositories.users import UsersRepository

    users_repo = UsersRepository(session)
    user = await users_repo.get_by_id(user_id)
    if not user or user.tg_id != tg_id:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    today = date.today()
    ui_builder = WishRequestUIService(session)
    ui = await ui_builder.build_for_user(user_tg_id=tg_id, pic_type="evening", day=today)

    await telegram_messenger.edit_message(
        chat_id=tg_id,
        message_id=callback.message.message_id,
        text=ui.text,
        reply_markup=ui.reply_markup,
    )
    await callback.answer("ℹ️ Выберите партнёра")


@router.callback_query(F.data.startswith("request_evening_"))
async def handle_request_evening(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
    settings: Settings,
    container: Container,
) -> None:
    """Handle evening request button."""
    tg_id = callback.from_user.id
    if callback.message:
        ok = await is_message_active(
            redis=container.redis,
            tg_id=tg_id,
            message_id=callback.message.message_id,
            kind=ActionKind.PROMPT,
        )
        if not ok:
            await telegram_messenger.remove_reply_markup(
                chat_id=tg_id,
                message_id=callback.message.message_id,
            )
            await callback.answer(get_message("CALLBACK_STALE_MESSAGE"), show_alert=True)
            return

    # Parse callback data: request_evening_{pair_id}_{user_id}
    parsed = parse_callback_data(callback.data, expected_parts=4, prefix="request_evening_")
    if not parsed:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    pair_id, user_id = parsed
    
    logger.info(
        "Processing request_evening callback",
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
    ui_builder = WishRequestUIService(session)
    
    # Send wish to partner
    success, partner_nickname = await send_wish_to_partner(
        session=session,
        pair=pair,
        user_id=user_id,
        tg_id=tg_id,
        pic_type="evening",
        today=today,
        telegram_messenger=telegram_messenger,
        redis=container.redis,
    )
    
    if not success:
        # Check if partner already sent
        daily_state = await daily_state_repo.get_by_pair_and_day(pair_id, today)
        if daily_state and daily_state.evening_initiator is not None:
            # Refresh UI (best effort) so the user sees "sent" status.
            try:
                ui = await ui_builder.build_for_user(
                    user_tg_id=tg_id, pic_type="evening", day=today
                )
                await telegram_messenger.edit_message(
                    chat_id=tg_id,
                    message_id=callback.message.message_id,
                    text=ui.text,
                    reply_markup=ui.reply_markup,
                )
            except Exception:
                pass
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
    
    # Success: refresh the aggregated prompt (no extra confirmation message in chat)
    ui = await ui_builder.build_for_user(user_tg_id=tg_id, pic_type="evening", day=today)
    await telegram_messenger.edit_message(
        chat_id=tg_id,
        message_id=callback.message.message_id,
        text=ui.text,
        reply_markup=ui.reply_markup,
    )

    # Also refresh partner's prompt message (best effort) so the send button disappears for this pair.
    partner_tg_id = user_b.tg_id if user_a.tg_id == tg_id else user_a.tg_id
    await refresh_aggregated_wish_prompt(
        session=session,
        telegram_messenger=telegram_messenger,
        tg_id=partner_tg_id,
        pic_type="evening",
        day=today,
    )
    
    # Schedule reminder tasks
    partner_tg_id = user_b.tg_id if user_a.tg_id == tg_id else user_a.tg_id
    recipient_user = user_b if user_a.id == user_id else user_a
    
    await schedule_reminder_tasks(
        pair_id=pair_id,
        initiator_tg_id=tg_id,
        recipient_tg_id=partner_tg_id,
        recipient_user_id=recipient_user.id,
        pic_type="evening",
        settings=settings,
    )
    
    await callback.answer("✅ Отправлено")

