"""Subscription renewal reminder tasks."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

from src.core.constants import PairStatus
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.models import User
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.services.messaging.partner_label import format_partner_label
from src.worker.di.context import WorkerContext

logger = get_logger(__name__)


async def send_renewal_reminders(ctx: dict[str, Any], worker_context: WorkerContext) -> None:
    """Send renewal reminders for subscriptions expiring soon.
    
    Sends reminders to users whose subscriptions expire within configured days.
    Reminders are sent every configured interval (default: 6 hours).
    Lifetime subscriptions are excluded.
    
    Args:
        ctx: Arq context
        worker_context: Worker context with dependencies
    """
    settings = worker_context.settings
    lock_service = worker_context.lock_service
    messenger = worker_context.messenger
    
    days_before = settings.subscription_renewal_days_before
    interval_hours = settings.subscription_renewal_reminder_interval_hours
    key_prefix = settings.redis_key_prefix_renewal_reminder
    
    today = date.today()
    expiry_threshold = today + timedelta(days=days_before)
    
    async with worker_context.session_factory() as session:
        subs_repo = SubscriptionsRepository(session)
        pairs_repo = PairsRepository(session)
        
        # Get active subscriptions expiring within threshold
        # Exclude lifetime subscriptions
        expiring_subs = await subs_repo.get_active_expiring_before(expiry_threshold)
        
        if not expiring_subs:
            logger.debug("No subscriptions expiring soon")
            return
        
        logger.info(
            "Found subscriptions expiring soon",
            count=len(expiring_subs),
            days_before=days_before,
            expiry_threshold=expiry_threshold.isoformat(),
        )
        
        sent_count = 0
        skipped_count = 0
        
        for sub in expiring_subs:
            try:
                # Skip lifetime subscriptions
                if sub.is_lifetime:
                    logger.debug(
                        "Skipping lifetime subscription",
                        subscription_id=sub.id,
                        pair_id=sub.pair_id,
                    )
                    skipped_count += 1
                    continue
                
                # Get pair
                pair = await pairs_repo.get_by_id(sub.pair_id)
                if not pair:
                    logger.warning(
                        "Pair not found for subscription",
                        subscription_id=sub.id,
                        pair_id=sub.pair_id,
                    )
                    continue
                
                # Only send for active pairs
                if pair.status != PairStatus.ACTIVE.value:
                    logger.debug(
                        "Skipping non-active pair",
                        pair_id=pair.id,
                        status=pair.status,
                    )
                    skipped_count += 1
                    continue
                
                # Calculate days left
                days_left = (sub.period_end - today).days
                
                # Only send if within threshold (1-3 days before expiry)
                # Do NOT send on expiry day (days_left = 0) or after
                if days_left > days_before or days_left <= 0:
                    logger.debug(
                        "Subscription not within threshold",
                        subscription_id=sub.id,
                        days_left=days_left,
                        days_before=days_before,
                    )
                    skipped_count += 1
                    continue
                
                # Check if reminder was sent recently (within interval)
                # Use daily key to track reminders per day
                reminder_key = f"{key_prefix}:{sub.pair_id}:{today.isoformat()}"
                last_reminder_timestamp = await lock_service.get_last_warning_time(
                    reminder_key,
                )
                
                if last_reminder_timestamp:
                    # Check if enough time has passed
                    import time
                    now_timestamp = time.time()
                    time_since_last = (now_timestamp - last_reminder_timestamp) / 3600  # hours
                    
                    if time_since_last < interval_hours:
                        logger.debug(
                            "Reminder sent recently, skipping",
                            subscription_id=sub.id,
                            pair_id=sub.pair_id,
                            hours_since_last=time_since_last,
                            interval_hours=interval_hours,
                        )
                        skipped_count += 1
                        continue
                
                # Get users
                user_a_result = await session.execute(
                    select(User).where(User.id == pair.uid_a)
                )
                user_a = user_a_result.scalar_one()
                user_b_result = await session.execute(
                    select(User).where(User.id == pair.uid_b)
                )
                user_b = user_b_result.scalar_one()
                
                # Build message
                # Russian pluralization for days
                if days_left == 1:
                    days_word = "день"
                elif days_left in (2, 3, 4):
                    days_word = "дня"
                else:
                    days_word = "дней"
                
                # Format partner labels
                label_for_a = format_partner_label(
                    partner_nickname=pairs_repo.get_my_nickname_for_partner(pair, user_a.id),
                    partner_username=user_b.username,
                )
                label_for_b = format_partner_label(
                    partner_nickname=pairs_repo.get_my_nickname_for_partner(pair, user_b.id),
                    partner_username=user_a.username,
                )
                
                # Build personalized reminder messages
                if label_for_a:
                    reminder_text_a = get_message(
                        "SUBSCRIPTION_RENEWAL_REMINDER_WITH_PARTNER",
                        days_left=days_left,
                        days_word=days_word,
                        partner_label=label_for_a,
                    )
                else:
                    reminder_text_a = get_message(
                        "SUBSCRIPTION_RENEWAL_REMINDER",
                        days_left=days_left,
                        days_word=days_word,
                    )
                
                if label_for_b:
                    reminder_text_b = get_message(
                        "SUBSCRIPTION_RENEWAL_REMINDER_WITH_PARTNER",
                        days_left=days_left,
                        days_word=days_word,
                        partner_label=label_for_b,
                    )
                else:
                    reminder_text_b = get_message(
                        "SUBSCRIPTION_RENEWAL_REMINDER",
                        days_left=days_left,
                        days_word=days_word,
                    )
                
                # Add pay button
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="💳 Оплатить",
                                callback_data="pay_now",
                            ),
                        ],
                    ],
                )
                
                # Send personalized reminders to both users
                await messenger.send_message(
                    chat_id=user_a.tg_id,
                    text=reminder_text_a,
                    reply_markup=keyboard,
                )
                await messenger.send_message(
                    chat_id=user_b.tg_id,
                    text=reminder_text_b,
                    reply_markup=keyboard,
                )
                
                # Mark reminder as sent
                import time
                now_timestamp = time.time()
                await lock_service.set_last_warning_time(reminder_key, now_timestamp)
                
                sent_count += 1
                
                logger.info(
                    "Renewal reminder sent",
                    subscription_id=sub.id,
                    pair_id=sub.pair_id,
                    days_left=days_left,
                    user_a_tg_id=user_a.tg_id,
                    user_b_tg_id=user_b.tg_id,
                )
                
            except Exception as e:
                logger.error(
                    "Error sending renewal reminder",
                    subscription_id=sub.id,
                    pair_id=sub.pair_id if sub else None,
                    error=str(e),
                    exc_info=True,
                )
        
        logger.info(
            "Renewal reminders processing completed",
            total_found=len(expiring_subs),
            sent=sent_count,
            skipped=skipped_count,
        )

