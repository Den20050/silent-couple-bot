"""Past due subscription tasks."""

from datetime import date
from typing import Any, Optional

from sqlalchemy import select

from src.core.constants import PairStatus
from src.core.logger import get_logger
from src.db.models import User
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.worker.di.context import WorkerContext
from src.worker.tasks.utils.state_checks import check_past_due_notification_needed

logger = get_logger(__name__)


async def check_and_update_expired_subscriptions(
    worker_context: WorkerContext,
    send_notifications: bool = False,
) -> None:
    """Check and update expired subscriptions to past_due status.
    
    Args:
        worker_context: Worker context with dependencies
        send_notifications: If True, send dunning notifications to users
    """
    async with worker_context.session_factory() as session:
        subs_repo = SubscriptionsRepository(session)
        pairs_repo = PairsRepository(session)
        
        past_due_subs = await subs_repo.get_past_due()
        
        if not past_due_subs:
            logger.info("No expired subscriptions found")
            return
        
        logger.info(
            "Found expired subscriptions",
            count=len(past_due_subs),
        )
        
        updated_count = 0
        for sub in past_due_subs:
            try:
                pair = await pairs_repo.get_by_id(sub.pair_id)
                if not pair:
                    continue
                
                # Only update if status is not already past_due
                if pair.status == PairStatus.PAST_DUE.value:
                    logger.debug(
                        "Pair already has past_due status, skipping",
                        pair_id=pair.id,
                    )
                    continue
                
                # Update pair status
                await pairs_repo.update_status(pair.id, PairStatus.PAST_DUE)
                updated_count += 1
                
                logger.info(
                    "Updated pair status to past_due",
                    pair_id=pair.id,
                    subscription_id=sub.id,
                    period_end=sub.period_end.isoformat(),
                )
                
                # Send notifications if requested
                if send_notifications:
                    # Get users
                    user_a_result = await session.execute(
                        select(User).where(User.id == pair.uid_a)
                    )
                    user_a = user_a_result.scalar_one()
                    user_b_result = await session.execute(
                        select(User).where(User.id == pair.uid_b)
                    )
                    user_b = user_b_result.scalar_one()
                    
                    # Send notifications using NotificationBuilder
                    messenger = worker_context.messenger
                    notification_builder = worker_context.notification_builder
                    
                    dunning_text, keyboard = await notification_builder.build_dunning_notification_message()
                    
                    await messenger.send_message(
                        chat_id=user_a.tg_id,
                        text=dunning_text,
                        reply_markup=keyboard,
                    )
                    await messenger.send_message(
                        chat_id=user_b.tg_id,
                        text=dunning_text,
                        reply_markup=keyboard,
                    )
                    
                    logger.info("Dunning notification sent", pair_id=pair.id)
                
                await session.commit()
            except Exception as e:
                logger.error(
                    "Error updating expired subscription",
                    pair_id=sub.pair_id,
                    subscription_id=sub.id,
                    error=str(e),
                    exc_info=True,
                )
                await session.rollback()
        
        logger.info(
            "Updated pairs to past_due status",
            total_expired=len(past_due_subs),
            updated=updated_count,
        )


async def dunning_notifications(ctx: dict[str, Any], worker_context: WorkerContext) -> None:
    """Send dunning notifications for past due subscriptions.
    
    Args:
        ctx: Arq context
        worker_context: Worker context with dependencies
    """
    await check_and_update_expired_subscriptions(
        worker_context=worker_context,
        send_notifications=True,
    )


async def send_past_due_notification(
    worker_context: WorkerContext,
    pair,
    subscription,
    today: date,
    pic_type: str = "morning",
) -> None:
    """Send past due notification for a pair.
    
    Args:
        worker_context: Worker context with dependencies
        pair: Pair object
        subscription: Subscription object
        today: Current date
        pic_type: Picture type ("morning" or "evening") - determines notification key
    """
    lock_service = worker_context.lock_service
    async with worker_context.session_factory() as session:
        # Check if notification should be sent
        should_send = await check_past_due_notification_needed(
            session=session,
            pair_id=pair.id,
            today=today,
            subscription=subscription,
            lock_service=lock_service,
            pic_type=pic_type,
        )
        
        if not should_send:
            return
        
        # Get users
        user_a_result = await session.execute(
            select(User).where(User.id == pair.uid_a)
        )
        user_a = user_a_result.scalar_one()
        user_b_result = await session.execute(
            select(User).where(User.id == pair.uid_b)
        )
        user_b = user_b_result.scalar_one()
        
        # Send notification using NotificationBuilder
        messenger = worker_context.messenger
        notification_builder = worker_context.notification_builder
        
        notification_text, reply_markup = await notification_builder.build_past_due_notification_message(
            include_button=True,
        )
        
        await messenger.send_message(
            chat_id=user_a.tg_id,
            text=notification_text,
            reply_markup=reply_markup,
        )
        await messenger.send_message(
            chat_id=user_b.tg_id,
            text=notification_text,
            reply_markup=reply_markup,
        )
        
        # Mark notification as sent
        days_since_expiry = (today - subscription.period_end).days
        
        if days_since_expiry <= 3:
            # First 3 days: mark as sent today (for both morning and evening)
            past_due_notification_key = (
                f"past_due_notification_{pic_type}:{pair.id}:{today.isoformat()}"
            )
            await lock_service.set_key_with_ttl(past_due_notification_key, "1", 86400)
            
            # Update subscription
            from src.db.repositories.subscriptions import SubscriptionsRepository
            subs_repo = SubscriptionsRepository(session)
            await subs_repo.update_last_past_due_notification_date(
                subscription.id,
                today,
            )
        else:
            # After 3 days: mark last notification date for this pic_type
            # Use separate keys for morning and evening to allow both in the same day
            last_notification_key = f"past_due_last_notification_{pic_type}:{pair.id}"
            await lock_service.set_key_with_ttl(
                last_notification_key,
                today.isoformat(),
                7 * 86400,
            )
            
            # Update subscription
            # Note: We update last_past_due_notification_date to today
            # This allows tracking when any notification was sent
            from src.db.repositories.subscriptions import SubscriptionsRepository
            subs_repo = SubscriptionsRepository(session)
            await subs_repo.update_last_past_due_notification_date(
                subscription.id,
                today,
            )
        
        await session.commit()
        
        logger.info(
            "Past due notification sent",
            pair_id=pair.id,
            days_since_expiry=days_since_expiry,
        )

