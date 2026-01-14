"""Callback query handlers."""

from datetime import date

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

import random

from src.core.constants import (
    PicType,
    MICRO_SURPRISE_MORNING_CAPTIONS,
    MICRO_SURPRISE_EVENING_CAPTIONS,
    MICRO_SURPRISE_MIN_HOURS,
    PairStatus,
)
from src.core.messages import get_message
from src.core.logger import get_logger
from src.core.config import Settings
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.image import ImageService
from src.services.telegram.messenger import TelegramMessenger

logger = get_logger(__name__)

router = Router(name="callbacks")


def get_caption_with_surprise(
    pair_mode: str,
    pic_type: str,
    daily_state,
) -> tuple[str, bool]:
    """Get caption with Micro-Surprise logic for Chat Mode.
    
    Returns:
        tuple: (caption, is_surprise_used)
    """
    from datetime import datetime
    
    if pair_mode != "chat":
        # Silent Mode: standard captions
        if pic_type == "morning":
            return get_message("CAPTION_SILENT_MORNING"), False
        else:  # evening
            return get_message("CAPTION_SILENT_EVENING"), False
    
    # Chat Mode: check for Micro-Surprise
    if pic_type == "morning":
        standard_caption = get_message("CAPTION_CHAT_MORNING")
        surprise_captions = MICRO_SURPRISE_MORNING_CAPTIONS
    else:  # evening
        standard_caption = get_message("CAPTION_CHAT_EVENING")
        surprise_captions = MICRO_SURPRISE_EVENING_CAPTIONS
    
    # Check if we should use surprise (1 in 4 chance, but only if >= 72 hours passed)
    use_surprise = False
    if random.randint(1, 4) == 1:
        if daily_state.last_surprise_at is None:
            # First time - allow surprise
            use_surprise = True
        else:
            # Check if >= 72 hours passed
            hours_passed = (datetime.utcnow() - daily_state.last_surprise_at).total_seconds() / 3600
            if hours_passed >= MICRO_SURPRISE_MIN_HOURS:
                use_surprise = True
    
    if use_surprise:
        caption = random.choice(surprise_captions)
        return caption, True
    else:
        return standard_caption, False


def format_caption_with_nickname(
    caption: str,
    pair,
    sender_user_id: int,
    pairs_repo,
) -> str:
    """Format caption with partner nickname at the beginning.
    
    Args:
        caption: Original caption text
        pair: Pair object
        sender_user_id: User ID of the sender (to determine which nickname to use)
        pairs_repo: PairsRepository instance
        
    Returns:
        Formatted caption with nickname prefix
    """
    # Get partner nickname (how recipient calls sender)
    partner_nickname = pairs_repo.get_partner_nickname(pair, sender_user_id)
    
    if partner_nickname:
        # Add nickname at the beginning: "от мама. Доброе утро!"
        return f"от {partner_nickname}. {caption}"
    else:
        # No nickname set, return original caption
        return caption


@router.callback_query(F.data.startswith("request_morning_all_"))
async def handle_request_morning_all(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle morning request button for all partners (user with multiple pairs)."""
    # Parse callback data: request_morning_all_{user_id}
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    try:
        user_id = int(parts[3])
    except (ValueError, IndexError) as e:
        logger.error(
            "Failed to parse callback_data",
            callback_data=callback.data,
            parts=parts,
            error=str(e),
        )
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    tg_id = callback.from_user.id
    
    logger.info(
        "Processing request_morning_all callback",
        user_id=user_id,
        tg_id=tg_id,
        callback_data=callback.data,
    )
    
    pairs_repo = PairsRepository(session)
    daily_state_repo = DailyStateRepository(session)
    users_repo = UsersRepository(session)
    
    # Get user
    user = await users_repo.get_by_id(user_id)
    if not user or user.tg_id != tg_id:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    # Get all active pairs for this user
    all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    active_pairs = [p for p in all_pairs if p.status in (PairStatus.TRIAL.value, PairStatus.ACTIVE.value)]
    
    if not active_pairs:
        await callback.answer("❌ У вас нет активных пар", show_alert=True)
        return
    
    today = date.today()
    image_service = ImageService(session)
    
    sent_count = 0
    failed_count = 0
    partner_nicknames = []
    
    # Send wish to all partners
    for pair in active_pairs:
        try:
            # Get users
            user_a = await users_repo.get_by_id(pair.uid_a)
            user_b = await users_repo.get_by_id(pair.uid_b)
            if not user_a or not user_b:
                failed_count += 1
                continue
            
            # Check if subscription is past due
            if pair.status == PairStatus.PAST_DUE.value:
                failed_count += 1
                continue
            
            # Get daily state
            daily_state = await daily_state_repo.get_or_create(pair.id, today)
            
            # Skip if already sent today
            if daily_state.morning_initiator is not None or daily_state.morning_sent_at is not None:
                continue
            
            # Get random image
            file_id = await image_service.get_random_image(pair.id, PicType.MORNING)
            if not file_id:
                failed_count += 1
                continue
            
            # Try to atomically set initiator
            success = await daily_state_repo.set_morning_initiator(
                pair_id=pair.id,
                day=today,
                initiator_id=user_id,
                file_id=file_id,
            )
            
            if not success:
                # Someone already pressed for this pair
                continue
            
            # Commit initiator setting
            await session.commit()
            
            # Get partner
            partner = user_b if user_a.tg_id == tg_id else user_a
            
            # Refresh daily_state
            daily_state = await daily_state_repo.get_by_pair_and_day(pair.id, today)
            
            # Get caption with Micro-Surprise logic
            caption, is_surprise = get_caption_with_surprise(
                pair_mode=pair.mode,
                pic_type="morning",
                daily_state=daily_state,
            )
            
            # Update last_surprise_at if surprise was used
            if is_surprise:
                await daily_state_repo.update_last_surprise_at(pair.id, today)
                await session.commit()
            
            # Format caption with nickname
            caption = format_caption_with_nickname(caption, pair, user_id, pairs_repo)
            
            button_text = get_message("RESPOND_BUTTON")
            initiator_tg_id = tg_id
            
            # Always send to bot DM
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": button_text,
                            "callback_data": f"tap_morning_{pair.id}_{initiator_tg_id}",
                        },
                    ],
                ],
            }
            
            await telegram_messenger.send_photo(
                chat_id=partner.tg_id,
                photo=file_id,
                caption=caption,
                reply_markup=reply_markup,
            )
            
            # Get partner nickname for confirmation message (nickname that user gave to partner)
            partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user_id)
            if partner_nickname:
                partner_nicknames.append(partner_nickname)
            else:
                # Fallback to "партнёру" if no nickname
                partner_nicknames.append("партнёру")
            
            sent_count += 1
            await session.commit()
        except Exception as e:
            logger.error(
                "Error sending morning wish to partner",
                pair_id=pair.id,
                error=str(e),
                exc_info=True,
            )
            failed_count += 1
            await session.rollback()
            continue
    
    # Edit message to show success with partner nicknames
    if sent_count > 0:
        # Format message with nicknames
        if len(partner_nicknames) == 1:
            message_text = f"✅ Вы отправили пожелание {partner_nicknames[0]}"
        elif len(partner_nicknames) == 2:
            message_text = f"✅ Вы отправили пожелание {partner_nicknames[0]} и {partner_nicknames[1]}"
        else:
            # For 3+ partners: "никнейм1, никнейм2 и никнейм3"
            last_nickname = partner_nicknames[-1]
            other_nicknames = ", ".join(partner_nicknames[:-1])
            message_text = f"✅ Вы отправили пожелание {other_nicknames} и {last_nickname}"
        
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
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    try:
    pair_id = int(parts[2])
    user_id = int(parts[3])
    except (ValueError, IndexError) as e:
        logger.error(
            "Failed to parse callback_data",
            callback_data=callback.data,
            parts=parts,
            error=str(e),
        )
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    tg_id = callback.from_user.id
    
    logger.info(
        "Processing request_morning callback",
        pair_id=pair_id,
        user_id=user_id,
        tg_id=tg_id,
        callback_data=callback.data,
        parts=parts,
    )
    
    pairs_repo = PairsRepository(session)
    daily_state_repo = DailyStateRepository(session)
    users_repo = UsersRepository(session)
    
    # Try to get pair with detailed logging
    pair = await pairs_repo.get_by_id(pair_id)
    if not pair:
        # Try to check if pair exists with different query
        from sqlalchemy import select
        from src.db.models import Pair
        stmt = select(Pair).where(Pair.id == pair_id)
        result = await session.execute(stmt)
        pair_check = result.scalar_one_or_none()
        
        logger.error(
            "Pair not found in handle_request_morning",
            pair_id=pair_id,
            user_id=user_id,
            tg_id=tg_id,
            callback_data=callback.data,
            pair_exists=(pair_check is not None),
            pair_status=pair_check.status if pair_check else None,
        )
        await callback.answer(get_message("CALLBACK_PAIR_NOT_FOUND"), show_alert=True)
        return
    
    logger.debug(
        "Pair found",
        pair_id=pair.id,
        pair_status=pair.status,
        uid_a=pair.uid_a,
        uid_b=pair.uid_b,
    )
    
    # Check if subscription is past due
    if pair.status == PairStatus.PAST_DUE.value:
        await callback.answer(
            get_message("WORKER_PAST_DUE_DUNNING"),
            show_alert=True
        )
        return
    
    # Get users by ID (pair.uid_a and pair.uid_b are user.id, not tg_id)
    user_a = await users_repo.get_by_id(pair.uid_a)
    user_b = await users_repo.get_by_id(pair.uid_b)
    if not user_a or not user_b:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    today = date.today()
    
    # Get daily state first (needed for Micro-Surprise check)
    daily_state = await daily_state_repo.get_or_create(pair_id, today)
    
    # Try to atomically set initiator
    image_service = ImageService(session)
    file_id = await image_service.get_random_image(pair_id, PicType.MORNING)
    
    if not file_id:
        await callback.answer(get_message("CALLBACK_NO_IMAGES_AVAILABLE"), show_alert=True)
        return
    
    success = await daily_state_repo.set_morning_initiator(
        pair_id=pair_id,
        day=today,
        initiator_id=user_id,
        file_id=file_id,
    )
    
    if not success:
        # Someone already pressed
        await callback.answer(get_message("CALLBACK_PARTNER_ALREADY_SENT"), show_alert=True)
        return
    
    # Commit initiator setting BEFORE sending photo
    # This ensures that even if photo sending fails, initiator is saved
    # and worker won't send duplicate requests
    await session.commit()
    
    # Success - edit messages
    # Get message IDs from pair (stored by worker)
    # For now, just edit the current message
    await telegram_messenger.edit_message(
        chat_id=tg_id,
        message_id=callback.message.message_id,
        text="✅ Вы отправили пожелание",
    )
    
    # Send photo to partner
    partner_tg_id = user_b.tg_id if user_a.tg_id == tg_id else user_a.tg_id
    
    # Refresh daily_state to get updated last_surprise_at (in new transaction)
    daily_state = await daily_state_repo.get_by_pair_and_day(pair_id, today)
    
    # Get caption with Micro-Surprise logic
    caption, is_surprise = get_caption_with_surprise(
        pair_mode=pair.mode,
        pic_type="morning",
        daily_state=daily_state,
    )
    
    # Update last_surprise_at if surprise was used
    if is_surprise:
        await daily_state_repo.update_last_surprise_at(pair_id, today)
        await session.commit()
    
    # Get sender user ID (to determine which nickname to use)
    sender_user = user_a if user_a.tg_id == tg_id else user_b
    sender_user_id = sender_user.id
    
    # Format caption with nickname at the beginning
    caption = format_caption_with_nickname(caption, pair, sender_user_id, pairs_repo)
    
    button_text = get_message("RESPOND_BUTTON")
    
    # Get initiator tg_id for callback_data (current user is the initiator)
    initiator_tg_id = tg_id
    
    try:
        # Always send to bot DM
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": button_text,
                            "callback_data": f"tap_morning_{pair_id}_{initiator_tg_id}",
                        },
                    ],
                ],
            }
        
        await telegram_messenger.send_photo(
            chat_id=partner_tg_id,
            photo=file_id,
            caption=caption,
            reply_markup=reply_markup,
            )
        # Commit after successful photo send
        await session.commit()
        
        # Schedule reminder tasks: 3, 6, 9 hours for recipient, 10+ hours for initiator
        try:
            from arq import create_pool
            from arq.connections import RedisSettings
            from datetime import timedelta
            
            # Get settings from container
            container = callback.bot.get("container")  # type: ignore
            if not container:
                raise RuntimeError(
                    "Container not available in context. "
                    "Ensure ContainerMiddleware is registered."
                )
            redis_url = container.settings.redis_url
            
            arq_redis = await create_pool(RedisSettings.from_dsn(redis_url))
            
            # Get recipient user ID
            recipient_user = user_b if user_a.id == user_id else user_a
            
            # Schedule recipient reminders at 3, 6, 9 hours
            for reminder_hours in [3, 6, 9]:
                await arq_redis.enqueue_job(
                    "send_recipient_reminder",
                    pair_id=pair_id,
                    recipient_tg_id=recipient_user.tg_id,
                    pic_type="morning",
                    hours=reminder_hours,
                    _defer_by=timedelta(hours=reminder_hours),
                )
            
            # Schedule initiator warnings starting from 10 hours, then every hour until 24 hours
            initiator_user = user_a if user_a.id == user_id else user_b
            recipient_username = recipient_user.username or str(recipient_user.tg_id)
            
            for warning_hours in range(10, 25):  # 10 to 24 hours
                await arq_redis.enqueue_job(
                    "send_initiator_warning",
                    pair_id=pair_id,
                    initiator_tg_id=initiator_user.tg_id,
                    recipient_username=recipient_username,
                    pic_type="morning",
                    hours=warning_hours,
                    _defer_by=timedelta(hours=warning_hours),
                )
            
            await arq_redis.close()
            
            logger.info(
                "Scheduled reminder tasks for morning picture",
                pair_id=pair_id,
                initiator_id=user_id,
                recipient_id=recipient_user.id,
            )
        except Exception as e:
            logger.error(
                "Failed to schedule reminder tasks",
                pair_id=pair_id,
                error=str(e),
                exc_info=True,
            )
            # Don't fail the whole operation if scheduling fails
    except Exception as e:
        # Log error but don't fail - initiator is already saved
        logger.error(
            "Failed to send morning photo to partner",
            pair_id=pair_id,
            partner_tg_id=partner_tg_id,
            file_id=file_id,
            error=str(e),
            exc_info=True,
        )
        # Try to send error message to user
        try:
            await telegram_messenger.send_message(
                chat_id=tg_id,
                text=get_message("CALLBACK_SEND_PICTURE_ERROR"),
            )
        except Exception:
            pass  # Ignore if we can't send error message
    
    await callback.answer()


@router.callback_query(F.data.startswith("tap_morning_"))
async def handle_tap_morning(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle morning tap (response)."""
    # Parse callback data: 
    # Old format: tap_morning_{pair_id}_{initiator_tg_id} (for regular responses)
    # New format: tap_morning_{pair_id}_{initiator_tg_id}_{day_iso} (for reminders)
    # Note: initiator_tg_id is the tg_id of the user who sent the picture
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    pair_id = int(parts[2])
    initiator_tg_id = int(parts[3])  # This is initiator's tg_id from callback_data
    
    # Check if day is included (for reminders)
    # Format: tap_morning_{pair_id}_{initiator_tg_id}|{day_iso}
    # Use "|" as separator to avoid splitting issues with "_"
    target_day = None
    if "|" in callback.data:
        try:
            from datetime import date as date_class
            # Split by "|" to get day part
            day_part = callback.data.split("|")[1]
            target_day = date_class.fromisoformat(day_part)
        except (ValueError, IndexError) as e:
            logger.warning(
                "Failed to parse day from callback_data",
                callback_data=callback.data,
                error=str(e),
            )
            # Fall back to today if parsing fails
            target_day = None
    
    tg_id = callback.from_user.id
    
    pairs_repo = PairsRepository(session)
    daily_state_repo = DailyStateRepository(session)
    users_repo = UsersRepository(session)
    
    pair = await pairs_repo.get_by_id(pair_id)
    if not pair:
        logger.warning(
            "Pair not found in handle_request_morning",
            pair_id=pair_id,
            user_id=user_id,
            tg_id=tg_id,
            callback_data=callback.data,
        )
        await callback.answer(get_message("CALLBACK_PAIR_NOT_FOUND"), show_alert=True)
        return
    
    # Check if subscription is past due
    if pair.status == PairStatus.PAST_DUE.value:
        await callback.answer(
            get_message("WORKER_PAST_DUE_DUNNING"),
            show_alert=True
        )
        return
    
    # Get users
    user_a = await users_repo.get_by_id(pair.uid_a)
    user_b = await users_repo.get_by_id(pair.uid_b)
    if not user_a or not user_b:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    # Verify that current user is part of the pair
    if tg_id not in [user_a.tg_id, user_b.tg_id]:
        await callback.answer(get_message("CALLBACK_ACCESS_DENIED"), show_alert=True)
        return
    
    # Determine which day to check
    # If target_day is provided (from reminder), use it; otherwise use today (for regular responses)
    check_day = target_day if target_day else date.today()
    
    logger.info(
        "Processing tap_morning callback",
        pair_id=pair_id,
        initiator_tg_id=initiator_tg_id,
        tg_id=tg_id,
        target_day=str(target_day) if target_day else None,
        check_day=str(check_day),
        callback_data=callback.data,
    )
    
    daily_state = await daily_state_repo.get_by_pair_and_day(pair_id, check_day)
    
    # Check if morning initiator exists (someone already sent)
    if not daily_state or daily_state.morning_initiator is None:
        logger.warning(
            "Morning initiator not found for tap_morning",
            pair_id=pair_id,
            check_day=str(check_day),
            target_day=str(target_day) if target_day else None,
        )
        await callback.answer(get_message("CALLBACK_WISH_NOT_SENT_YET"), show_alert=True)
        return
    
    # Check if already responded
    if daily_state.morning_responded_at is not None:
        await callback.answer(get_message("CALLBACK_ALREADY_RESPONDED"), show_alert=True)
        return
    
    # Check if the current user is the initiator (can't respond to own message)
    # Use initiator_tg_id from callback_data, not daily_state.morning_initiator,
    # because daily_state.morning_initiator might have changed if user sent their own wish
    # after receiving the reminder
    current_user = await users_repo.get_by_tg_id(tg_id)
    if not current_user:
        await callback.answer(get_message("CALLBACK_USER_NOT_FOUND"), show_alert=True)
        return
    
    # Verify that initiator_tg_id from callback_data matches the current initiator in daily_state
    # This ensures we're responding to the correct wish
    initiator_user = await users_repo.get_by_tg_id(initiator_tg_id)
    if not initiator_user:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    # Check if current user is trying to respond to their own wish
    if initiator_tg_id == tg_id:
        await callback.answer(get_message("CALLBACK_ALREADY_SENT_WISH"), show_alert=True)
        return
    
    # Verify that the initiator from callback_data is still the current initiator
    # (user might have sent their own wish after receiving reminder)
    if daily_state.morning_initiator != initiator_user.id:
        # The initiator has changed - partner might have sent their own wish
        # Check if current user is now the initiator
        if daily_state.morning_initiator == current_user.id:
            await callback.answer(get_message("CALLBACK_PARTNER_ALREADY_SENT"), show_alert=True)
        else:
            await callback.answer(get_message("CALLBACK_WISH_NOT_SENT_YET"), show_alert=True)
        return
    
    # Mark response (use check_day, not today, to handle reminders for previous days)
    success = await daily_state_repo.set_morning_response(pair_id, check_day)
    if not success:
        await callback.answer(get_message("CALLBACK_SAVE_RESPONSE_ERROR"), show_alert=True)
        return
    
    # Get random image for response
    image_service = ImageService(session)
    file_id = await image_service.get_random_image(pair_id, PicType.MORNING)
    
    if not file_id:
        await callback.answer(get_message("CALLBACK_NO_IMAGES_AVAILABLE"), show_alert=True)
        return
    
    # Send response photo to initiator
    initiator_user = user_a if daily_state.morning_initiator == user_a.id else user_b
    initiator_tg_id = initiator_user.tg_id
    
    # Different caption for Chat Mode vs Silent Mode
    if pair.mode == "chat":
        caption = get_message("RESPONSE_RECEIVED_CHAT")
    else:
        caption = get_message("RESPONSE_MORNING_SILENT")
    
    # Get sender user ID (recipient is responding, so sender is recipient)
    sender_user = user_a if user_a.tg_id == tg_id else user_b
    sender_user_id = sender_user.id
    
    # Format caption with nickname at the beginning
    caption = format_caption_with_nickname(caption, pair, sender_user_id, pairs_repo)
    
    # Always send to bot DM
    await telegram_messenger.send_photo(
        chat_id=initiator_tg_id,
        photo=file_id,
        caption=caption,
    )
    
    # Remove button from the message (keep message as is)
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


@router.callback_query(F.data.startswith("request_evening_all_"))
async def handle_request_evening_all(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle evening request button for all partners (user with multiple pairs)."""
    # Parse callback data: request_evening_all_{user_id}
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    try:
        user_id = int(parts[3])
    except (ValueError, IndexError) as e:
        logger.error(
            "Failed to parse callback_data",
            callback_data=callback.data,
            parts=parts,
            error=str(e),
        )
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    tg_id = callback.from_user.id
    
    logger.info(
        "Processing request_evening_all callback",
        user_id=user_id,
        tg_id=tg_id,
        callback_data=callback.data,
    )
    
    pairs_repo = PairsRepository(session)
    daily_state_repo = DailyStateRepository(session)
    users_repo = UsersRepository(session)
    
    # Get user
    user = await users_repo.get_by_id(user_id)
    if not user or user.tg_id != tg_id:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    # Get all active pairs for this user
    all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    active_pairs = [p for p in all_pairs if p.status in (PairStatus.TRIAL.value, PairStatus.ACTIVE.value)]
    
    if not active_pairs:
        await callback.answer("❌ У вас нет активных пар", show_alert=True)
        return
    
    today = date.today()
    image_service = ImageService(session)
    
    sent_count = 0
    failed_count = 0
    partner_nicknames = []  # Store nicknames of partners who received wishes
    
    # Send wish to all partners
    for pair in active_pairs:
        try:
            # Get users
            user_a = await users_repo.get_by_id(pair.uid_a)
            user_b = await users_repo.get_by_id(pair.uid_b)
            if not user_a or not user_b:
                failed_count += 1
                continue
            
            # Check if subscription is past due
            if pair.status == PairStatus.PAST_DUE.value:
                failed_count += 1
                continue
            
            # Get daily state
            daily_state = await daily_state_repo.get_or_create(pair.id, today)
            
            # Skip if already sent today
            if daily_state.evening_initiator is not None or daily_state.evening_sent_at is not None:
                continue
            
            # Get random image
            file_id = await image_service.get_random_image(pair.id, PicType.EVENING)
            if not file_id:
                failed_count += 1
                continue
            
            # Try to atomically set initiator
            success = await daily_state_repo.set_evening_initiator(
                pair_id=pair.id,
                day=today,
                initiator_id=user_id,
                file_id=file_id,
            )
            
            if not success:
                # Someone already pressed for this pair
                continue
            
            # Commit initiator setting
            await session.commit()
            
            # Get partner
            partner = user_b if user_a.tg_id == tg_id else user_a
            
            # Refresh daily_state
            daily_state = await daily_state_repo.get_by_pair_and_day(pair.id, today)
            
            # Get caption with Micro-Surprise logic
            caption, is_surprise = get_caption_with_surprise(
                pair_mode=pair.mode,
                pic_type="evening",
                daily_state=daily_state,
            )
            
            # Update last_surprise_at if surprise was used
            if is_surprise:
                await daily_state_repo.update_last_surprise_at(pair.id, today)
                await session.commit()
            
            # Format caption with nickname
            caption = format_caption_with_nickname(caption, pair, user_id, pairs_repo)
            
            button_text = get_message("RESPOND_BUTTON")
            initiator_tg_id = tg_id
            
            # Always send to bot DM
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": button_text,
                            "callback_data": f"tap_evening_{pair.id}_{initiator_tg_id}",
                        },
                    ],
                ],
            }
            
            await telegram_messenger.send_photo(
                chat_id=partner.tg_id,
                photo=file_id,
                caption=caption,
                reply_markup=reply_markup,
            )
            
            # Get partner nickname for confirmation message (nickname that user gave to partner)
            partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user_id)
            if partner_nickname:
                partner_nicknames.append(partner_nickname)
            else:
                # Fallback to "партнёру" if no nickname
                partner_nicknames.append("партнёру")
            
            sent_count += 1
            await session.commit()
        except Exception as e:
            logger.error(
                "Error sending evening wish to partner",
                pair_id=pair.id,
                error=str(e),
                exc_info=True,
            )
            failed_count += 1
            await session.rollback()
            continue
    
    # Edit message to show success with partner nicknames
    if sent_count > 0:
        # Format message with nicknames
        if len(partner_nicknames) == 1:
            message_text = f"✅ Вы отправили пожелание {partner_nicknames[0]}"
        elif len(partner_nicknames) == 2:
            message_text = f"✅ Вы отправили пожелание {partner_nicknames[0]} и {partner_nicknames[1]}"
        else:
            # For 3+ partners: "никнейм1, никнейм2 и никнейм3"
            last_nickname = partner_nicknames[-1]
            other_nicknames = ", ".join(partner_nicknames[:-1])
            message_text = f"✅ Вы отправили пожелание {other_nicknames} и {last_nickname}"
        
        await telegram_messenger.edit_message(
            chat_id=tg_id,
            message_id=callback.message.message_id,
            text=message_text,
        )
        await callback.answer()
    else:
        await callback.answer("❌ Не удалось отправить пожелания", show_alert=True)


@router.callback_query(F.data.startswith("request_evening_"))
async def handle_request_evening(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
    settings: Settings,
) -> None:
    """Handle evening request button."""
    # Parse callback data: request_evening_{pair_id}_{user_id}
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    try:
    pair_id = int(parts[2])
    user_id = int(parts[3])
    except (ValueError, IndexError) as e:
        logger.error(
            "Failed to parse callback_data in handle_request_evening",
            callback_data=callback.data,
            parts=parts,
            error=str(e),
        )
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    tg_id = callback.from_user.id
    
    logger.info(
        "Processing request_evening callback",
        pair_id=pair_id,
        user_id=user_id,
        tg_id=tg_id,
        callback_data=callback.data,
        parts=parts,
    )
    
    pairs_repo = PairsRepository(session)
    daily_state_repo = DailyStateRepository(session)
    users_repo = UsersRepository(session)
    
    # Try to get pair with detailed logging
    pair = await pairs_repo.get_by_id(pair_id)
    if not pair:
        # Try to check if pair exists with different query
        from sqlalchemy import select
        from src.db.models import Pair
        stmt = select(Pair).where(Pair.id == pair_id)
        result = await session.execute(stmt)
        pair_check = result.scalar_one_or_none()
        
        logger.error(
            "Pair not found in handle_request_evening",
            pair_id=pair_id,
            user_id=user_id,
            tg_id=tg_id,
            callback_data=callback.data,
            pair_exists=(pair_check is not None),
            pair_status=pair_check.status if pair_check else None,
        )
        await callback.answer(get_message("CALLBACK_PAIR_NOT_FOUND"), show_alert=True)
        return
    
    logger.debug(
        "Pair found in handle_request_evening",
        pair_id=pair.id,
        pair_status=pair.status,
        uid_a=pair.uid_a,
        uid_b=pair.uid_b,
    )
    
    # Check if subscription is past due
    if pair.status == PairStatus.PAST_DUE.value:
        await callback.answer(
            get_message("WORKER_PAST_DUE_DUNNING"),
            show_alert=True
        )
        return
    
    # Get users by ID (pair.uid_a and pair.uid_b are user.id, not tg_id)
    user_a = await users_repo.get_by_id(pair.uid_a)
    user_b = await users_repo.get_by_id(pair.uid_b)
    if not user_a or not user_b:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    today = date.today()
    
    # Get daily state first (needed for Micro-Surprise check)
    daily_state = await daily_state_repo.get_or_create(pair_id, today)
    
    # Try to atomically set initiator
    image_service = ImageService(session)
    file_id = await image_service.get_random_image(pair_id, PicType.EVENING)
    
    if not file_id:
        await callback.answer(get_message("CALLBACK_NO_IMAGES_AVAILABLE"), show_alert=True)
        return
    
    # Log file_id for debugging
    logger.info(
        "Evening request: got file_id",
        pair_id=pair_id,
        user_id=user_id,
        tg_id=tg_id,
        file_id=file_id[:20] + "..." if len(file_id) > 20 else file_id,
    )
    
    success = await daily_state_repo.set_evening_initiator(
        pair_id=pair_id,
        day=today,
        initiator_id=user_id,
        file_id=file_id,
    )
    
    if not success:
        # Someone already pressed
        await callback.answer(get_message("CALLBACK_PARTNER_ALREADY_SENT"), show_alert=True)
        return
    
    # Commit initiator setting BEFORE sending photo
    # This ensures that even if photo sending fails, initiator is saved
    # and worker won't send duplicate requests
    await session.commit()
    
    # Success - edit messages
    await telegram_messenger.edit_message(
        chat_id=tg_id,
        message_id=callback.message.message_id,
        text="✅ Вы отправили пожелание",
    )
    
    # Send photo to partner
    partner_tg_id = user_b.tg_id if user_a.tg_id == tg_id else user_a.tg_id
    
    # Refresh daily_state to get updated last_surprise_at (in new transaction)
    daily_state = await daily_state_repo.get_by_pair_and_day(pair_id, today)
    
    # Get caption with Micro-Surprise logic
    caption, is_surprise = get_caption_with_surprise(
        pair_mode=pair.mode,
        pic_type="evening",
        daily_state=daily_state,
    )
    
    # Update last_surprise_at if surprise was used
    if is_surprise:
        await daily_state_repo.update_last_surprise_at(pair_id, today)
        await session.commit()
    
    # Get sender user ID (to determine which nickname to use)
    sender_user = user_a if user_a.tg_id == tg_id else user_b
    sender_user_id = sender_user.id
    
    # Format caption with nickname at the beginning
    caption = format_caption_with_nickname(caption, pair, sender_user_id, pairs_repo)
    
    button_text = get_message("RESPOND_BUTTON")
    
    # Get initiator tg_id for callback_data (current user is the initiator)
    initiator_tg_id = tg_id
    
    try:
        # Always send to bot DM
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": button_text,
                            "callback_data": f"tap_evening_{pair_id}_{initiator_tg_id}",
                        },
                    ],
                ],
            }
        
        await telegram_messenger.send_photo(
            chat_id=partner_tg_id,
            photo=file_id,
            caption=caption,
            reply_markup=reply_markup,
            )
        # Commit after successful photo send
        await session.commit()
        
        # Schedule reminder tasks: 3, 6, 9 hours for recipient, 10+ hours for initiator
        try:
            from arq import create_pool
            from arq.connections import RedisSettings
            from datetime import timedelta
            
            redis_url = settings.redis_url
            
            arq_redis = await create_pool(RedisSettings.from_dsn(redis_url))
            
            # Get recipient user ID
            recipient_user = user_b if user_a.id == user_id else user_a
            
            # Schedule recipient reminders at 3, 6, 9 hours
            for reminder_hours in [3, 6, 9]:
                await arq_redis.enqueue_job(
                    "send_recipient_reminder",
                    pair_id=pair_id,
                    recipient_tg_id=recipient_user.tg_id,
                    pic_type="evening",
                    hours=reminder_hours,
                    _defer_by=timedelta(hours=reminder_hours),
                )
            
            # Schedule initiator warnings starting from 10 hours, then every hour until 24 hours
            initiator_user = user_a if user_a.id == user_id else user_b
            recipient_username = recipient_user.username or str(recipient_user.tg_id)
            
            for warning_hours in range(10, 25):  # 10 to 24 hours
                await arq_redis.enqueue_job(
                    "send_initiator_warning",
                    pair_id=pair_id,
                    initiator_tg_id=initiator_user.tg_id,
                    recipient_username=recipient_username,
                    pic_type="evening",
                    hours=warning_hours,
                    _defer_by=timedelta(hours=warning_hours),
                )
            
            await arq_redis.close()
            
            logger.info(
                "Scheduled reminder tasks for evening picture",
                pair_id=pair_id,
                initiator_id=user_id,
                recipient_id=recipient_user.id,
            )
        except Exception as e:
            logger.error(
                "Failed to schedule reminder tasks",
                pair_id=pair_id,
                error=str(e),
                exc_info=True,
            )
            # Don't fail the whole operation if scheduling fails
    except Exception as e:
        # Log error but don't fail - initiator is already saved
        logger.error(
            "Failed to send evening photo to partner",
            pair_id=pair_id,
            partner_tg_id=partner_tg_id,
            file_id=file_id,
            error=str(e),
            exc_info=True,
        )
        # Try to send error message to user
        try:
            await telegram_messenger.send_message(
                chat_id=tg_id,
                text=get_message("CALLBACK_SEND_PICTURE_ERROR"),
            )
        except Exception:
            pass  # Ignore if we can't send error message
    
    await callback.answer()


@router.callback_query(F.data.startswith("tap_evening_"))
async def handle_tap_evening(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle evening tap (response)."""
    # Parse callback data: 
    # Old format: tap_evening_{pair_id}_{initiator_tg_id} (for regular responses)
    # New format: tap_evening_{pair_id}_{initiator_tg_id}_{day_iso} (for reminders)
    # Note: initiator_tg_id is the tg_id of the user who sent the picture
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    pair_id = int(parts[2])
    initiator_tg_id = int(parts[3])  # This is initiator's tg_id from callback_data
    
    # Check if day is included (for reminders)
    # Format: tap_evening_{pair_id}_{initiator_tg_id}|{day_iso}
    # Use "|" as separator to avoid splitting issues with "_"
    target_day = None
    if "|" in callback.data:
        try:
            from datetime import date as date_class
            # Split by "|" to get day part
            day_part = callback.data.split("|")[1]
            target_day = date_class.fromisoformat(day_part)
        except (ValueError, IndexError) as e:
            logger.warning(
                "Failed to parse day from callback_data",
                callback_data=callback.data,
                error=str(e),
            )
            # Fall back to today if parsing fails
            target_day = None
    
    tg_id = callback.from_user.id
    
    pairs_repo = PairsRepository(session)
    daily_state_repo = DailyStateRepository(session)
    users_repo = UsersRepository(session)
    
    pair = await pairs_repo.get_by_id(pair_id)
    if not pair:
        logger.warning(
            "Pair not found in handle_request_morning",
            pair_id=pair_id,
            user_id=user_id,
            tg_id=tg_id,
            callback_data=callback.data,
        )
        await callback.answer(get_message("CALLBACK_PAIR_NOT_FOUND"), show_alert=True)
        return
    
    # Check if subscription is past due
    if pair.status == PairStatus.PAST_DUE.value:
        await callback.answer(
            get_message("WORKER_PAST_DUE_DUNNING"),
            show_alert=True
        )
        return
    
    # Get users
    user_a = await users_repo.get_by_id(pair.uid_a)
    user_b = await users_repo.get_by_id(pair.uid_b)
    if not user_a or not user_b:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    # Verify that current user is part of the pair
    if tg_id not in [user_a.tg_id, user_b.tg_id]:
        await callback.answer(get_message("CALLBACK_ACCESS_DENIED"), show_alert=True)
        return
    
    # Determine which day to check
    # If target_day is provided (from reminder), use it; otherwise use today (for regular responses)
    check_day = target_day if target_day else date.today()
    
    logger.info(
        "Processing tap_evening callback",
        pair_id=pair_id,
        initiator_tg_id=initiator_tg_id,
        tg_id=tg_id,
        target_day=str(target_day) if target_day else None,
        check_day=str(check_day),
        callback_data=callback.data,
    )
    
    daily_state = await daily_state_repo.get_by_pair_and_day(pair_id, check_day)
    
    # Check if evening initiator exists (someone already sent)
    if not daily_state or daily_state.evening_initiator is None:
        logger.warning(
            "Evening initiator not found for tap_evening",
            pair_id=pair_id,
            check_day=str(check_day),
            target_day=str(target_day) if target_day else None,
        )
        await callback.answer(get_message("CALLBACK_WISH_NOT_SENT_YET"), show_alert=True)
        return
    
    # Check if already responded
    if daily_state.evening_responded_at is not None:
        await callback.answer(get_message("CALLBACK_ALREADY_RESPONDED"), show_alert=True)
        return
    
    # Check if the current user is the initiator (can't respond to own message)
    # Use initiator_tg_id from callback_data, not daily_state.evening_initiator,
    # because daily_state.evening_initiator might have changed if user sent their own wish
    # after receiving the reminder
    current_user = await users_repo.get_by_tg_id(tg_id)
    if not current_user:
        await callback.answer(get_message("CALLBACK_USER_NOT_FOUND"), show_alert=True)
        return
    
    # Verify that initiator_tg_id from callback_data matches the current initiator in daily_state
    # This ensures we're responding to the correct wish
    initiator_user = await users_repo.get_by_tg_id(initiator_tg_id)
    if not initiator_user:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    # Check if current user is trying to respond to their own wish
    if initiator_tg_id == tg_id:
        await callback.answer(get_message("CALLBACK_ALREADY_SENT_WISH"), show_alert=True)
        return
    
    # Verify that the initiator from callback_data is still the current initiator
    # (user might have sent their own wish after receiving reminder)
    if daily_state.evening_initiator != initiator_user.id:
        # The initiator has changed - partner might have sent their own wish
        # Check if current user is now the initiator
        if daily_state.evening_initiator == current_user.id:
            await callback.answer(get_message("CALLBACK_PARTNER_ALREADY_SENT"), show_alert=True)
        else:
            await callback.answer(get_message("CALLBACK_WISH_NOT_SENT_YET"), show_alert=True)
        return
    
    # Mark response (use check_day, not today, to handle reminders for previous days)
    success = await daily_state_repo.set_evening_response(pair_id, check_day)
    if not success:
        await callback.answer(get_message("CALLBACK_SAVE_RESPONSE_ERROR"), show_alert=True)
        return
    
    # Get random image for response
    image_service = ImageService(session)
    file_id = await image_service.get_random_image(pair_id, PicType.EVENING)
    
    if not file_id:
        await callback.answer(get_message("CALLBACK_NO_IMAGES_AVAILABLE"), show_alert=True)
        return
    
    # Send response photo to initiator
    initiator_user = user_a if daily_state.evening_initiator == user_a.id else user_b
    initiator_tg_id = initiator_user.tg_id
    
    # Different caption for Chat Mode vs Silent Mode
    if pair.mode == "chat":
        caption = get_message("RESPONSE_RECEIVED_CHAT")
    else:
        caption = get_message("RESPONSE_EVENING_SILENT")
    
    # Get sender user ID (recipient is responding, so sender is recipient)
    sender_user = user_a if user_a.tg_id == tg_id else user_b
    sender_user_id = sender_user.id
    
    # Format caption with nickname at the beginning
    caption = format_caption_with_nickname(caption, pair, sender_user_id, pairs_repo)
    
    # Always send to bot DM
    await telegram_messenger.send_photo(
        chat_id=initiator_tg_id,
        photo=file_id,
        caption=caption,
    )
    
    # Remove button from the message (keep message as is)
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
        # Remove prefix "cancel_initiator_warnings_" and split remaining
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
    callback: CallbackQuery, session: AsyncSession
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

