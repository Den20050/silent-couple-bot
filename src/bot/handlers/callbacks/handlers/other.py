"""Other callback handlers."""

from datetime import date

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.messages import get_message
from src.core.logger import get_logger
from src.core.config import settings
from src.services.telegram.messenger import TelegramMessenger
from src.services.messaging.ui.wish_request_ui import WishRequestUIService

logger = get_logger(__name__)

router = Router(name="other_callbacks")


@router.callback_query(F.data.startswith("wish_sent_"))
async def handle_wish_sent_noop(callback: CallbackQuery) -> None:
    """Handle disabled 'sent' buttons in aggregated wish request prompts."""
    await callback.answer("✅ Уже отправлено")


@router.callback_query(F.data.startswith("wish_back_"))
async def handle_wish_back(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Return from pay explanation back to the aggregated wish request list."""
    # Format: wish_back_{pic_type}
    try:
        pic_type = callback.data.replace("wish_back_", "", 1)
    except Exception:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    if pic_type not in ("morning", "evening"):
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    tg_id = callback.from_user.id
    ui_builder = WishRequestUIService(session)
    ui = await ui_builder.build_for_user(user_tg_id=tg_id, pic_type=pic_type, day=date.today())

    await telegram_messenger.edit_message(
        chat_id=tg_id,
        message_id=callback.message.message_id,
        text=ui.text,
        reply_markup=ui.reply_markup,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wish_pay_"))
async def handle_wish_pay(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Show 'demo/subscription ended' explanation and a pay button for this pair."""
    # Format: wish_pay_{pic_type}_{pair_id}
    raw = callback.data.replace("wish_pay_", "", 1)
    parts = raw.split("_", 1)
    if len(parts) != 2:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    pic_type, pair_id_raw = parts
    if pic_type not in ("morning", "evening"):
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    try:
        pair_id = int(pair_id_raw)
    except ValueError:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    tg_id = callback.from_user.id

    from src.db.repositories.pairs import PairsRepository
    from src.db.repositories.users import UsersRepository
    from src.bot.handlers.start.services.pair_service import format_partner_text

    pairs_repo = PairsRepository(session)
    users_repo = UsersRepository(session)

    user = await users_repo.get_by_tg_id(tg_id)
    pair = await pairs_repo.get_by_id(pair_id)
    if not user or not pair:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    if user.id not in (pair.uid_a, pair.uid_b):
        await callback.answer(get_message("CALLBACK_ACCESS_DENIED"), show_alert=True)
        return

    if pair.status != "past_due":
        # Pair is no longer past due; refresh the list.
        ui_builder = WishRequestUIService(session)
        ui = await ui_builder.build_for_user(user_tg_id=tg_id, pic_type=pic_type, day=date.today())
        await telegram_messenger.edit_message(
            chat_id=tg_id,
            message_id=callback.message.message_id,
            text=ui.text,
            reply_markup=ui.reply_markup,
        )
        await callback.answer()
        return

    partner_id = pair.uid_b if pair.uid_a == user.id else pair.uid_a
    partner = await users_repo.get_by_id(partner_id)
    partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user.id)
    partner_text = format_partner_text(partner.username if partner else None, partner_nickname)

    text = get_message("WORKER_WISH_PAY_EXPIRED", partner_text=partner_text)
    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": get_message("WORKER_WISH_PAY_BUTTON"),
                    "callback_data": f"pay_select_currency_{pair_id}",
                }
            ],
            [
                {
                    "text": get_message("WORKER_WISH_BACK_BUTTON"),
                    "callback_data": f"wish_back_{pic_type}",
                }
            ],
        ]
    }

    await telegram_messenger.edit_message(
        chat_id=tg_id,
        message_id=callback.message.message_id,
        text=text,
        reply_markup=reply_markup,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_initiator_warnings_"))
async def handle_cancel_initiator_warnings(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle cancel initiator warnings button."""
    try:
        logger.info(
            "Cancel initiator warnings callback received",
            callback_data=callback.data,
            tg_id=callback.from_user.id,
        )
        
        # Parse callback data: cancel_initiator_warnings_{pair_id}_{day}_{pic_type}
        # Format: cancel_initiator_warnings_123_2025-01-15_morning
        data_without_prefix = callback.data.replace("cancel_initiator_warnings_", "", 1)
        parts = data_without_prefix.split("_", 2)  # Split into max 3 parts: pair_id, day, pic_type
        if len(parts) < 3:
            logger.warning(
                "Invalid callback data format",
                callback_data=callback.data,
                parts_count=len(parts),
            )
            await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
            return
        
        pair_id = int(parts[0])
        day_str = parts[1]  # Format: YYYY-MM-DD (date as string)
        pic_type = parts[2]  # morning or evening
        
        logger.info(
            "Parsed callback data",
            pair_id=pair_id,
            day_str=day_str,
            pic_type=pic_type,
        )
        
        tg_id = callback.from_user.id
        
        from src.db.repositories.pairs import PairsRepository
        from src.db.repositories.users import UsersRepository
        
        pairs_repo = PairsRepository(session)
        users_repo = UsersRepository(session)
        
        pair = await pairs_repo.get_by_id(pair_id)
        if not pair:
            logger.warning("Pair not found", pair_id=pair_id)
            await callback.answer(get_message("CALLBACK_PAIR_NOT_FOUND"), show_alert=True)
            return
        
        # Get users
        user_a = await users_repo.get_by_id(pair.uid_a)
        user_b = await users_repo.get_by_id(pair.uid_b)
        if not user_a or not user_b:
            logger.warning("Users not found", pair_id=pair_id)
            await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
            return
        
        # Verify that current user is part of this pair
        current_user = await users_repo.get_by_tg_id(tg_id)
        if not current_user:
            logger.warning("Current user not found", tg_id=tg_id)
            await callback.answer(get_message("CALLBACK_USER_NOT_FOUND"), show_alert=True)
            return
        
        if current_user.id != user_a.id and current_user.id != user_b.id:
            logger.warning(
                "Access denied",
                tg_id=tg_id,
                pair_id=pair_id,
                user_a_id=user_a.id,
                user_b_id=user_b.id,
            )
            await callback.answer(get_message("CALLBACK_ACCESS_DENIED"), show_alert=True)
            return
        
        # Save cancellation in Redis
        try:
            from src.core.redis_client import create_redis_client
            redis_client = await create_redis_client(socket_connect_timeout=2, socket_timeout=2)
            
            if redis_client:
                cancel_key = (
                    f"{settings.redis_key_prefix_warning_cancelled}:{pair_id}:{day_str}:{pic_type}"
                )
                # Store at least for the full warning horizon, so warnings don't resume.
                ttl_seconds = settings.warning_ttl_days * 24 * 3600
                await redis_client.setex(cancel_key, ttl_seconds, "1")
                # Verify the key was saved
                saved_value = await redis_client.get(cancel_key)
                logger.info(
                    "Cancellation saved in Redis",
                    cancel_key=cancel_key,
                    pair_id=pair_id,
                    day_str=day_str,
                    pic_type=pic_type,
                    saved_value=saved_value,
                    ttl=await redis_client.ttl(cancel_key),
                )
                await redis_client.aclose()
        except Exception as e:
            logger.warning("Failed to save cancellation in Redis", error=str(e), exc_info=True)
        
        # Edit message to confirm cancellation
        await telegram_messenger.edit_message(
            chat_id=tg_id,
            message_id=callback.message.message_id,
            text="✅ Напоминания отменены. Вы больше не будете получать уведомления об этом пожелании.",
            reply_markup=None,
        )
        
        await callback.answer(get_message("CALLBACK_REMINDERS_CANCELLED_SHORT"))
        logger.info("Cancel initiator warnings completed successfully", pair_id=pair_id, tg_id=tg_id)
    except Exception as e:
        logger.error(
            "Error handling cancel initiator warnings",
            callback_data=callback.data,
            tg_id=callback.from_user.id,
            error=str(e),
            exc_info=True,
        )
        try:
            await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        except Exception:
            pass  # Ignore errors when answering callback

