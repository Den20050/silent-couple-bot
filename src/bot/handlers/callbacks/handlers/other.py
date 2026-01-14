"""Other callback handlers."""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.messages import get_message
from src.core.logger import get_logger
from src.services.telegram.messenger import TelegramMessenger

logger = get_logger(__name__)

router = Router(name="other_callbacks")


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
                cancel_key = f"initiator_warning_cancelled:{pair_id}:{day_str}:{pic_type}"
                # Store for 48 hours (until next day)
                await redis_client.setex(cancel_key, 48 * 3600, "1")
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


@router.callback_query(F.data == "delete_confirm")
async def handle_delete_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Handle delete confirmation."""
    try:
        from src.bot.handlers.delete import cmd_delete

        # Create a fake message from callback
        message = callback.message
        message.text = "/delete"
        message.from_user = callback.from_user

        await cmd_delete(message, session)
        await callback.answer()
    except Exception as e:
        logger.error(
            "Error in handle_delete_confirm", error=str(e), exc_info=True
        )
        await callback.answer(get_message("MENU_ERROR"), show_alert=True)

