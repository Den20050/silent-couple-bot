"""Past due subscription tasks."""

from datetime import date
from typing import Any

from sqlalchemy import select

from src.core.constants import PairStatus
from src.core.logger import get_logger
from src.db.models import User
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.services.messaging.partner_label import format_partner_label
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
        today = date.today()
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
                
                # Update pair status and commit immediately
                # This ensures status is updated even if notification fails
                await pairs_repo.update_status(pair.id, PairStatus.PAST_DUE)
                await session.commit()
                updated_count += 1
                
                logger.info(
                    "Updated pair status to past_due",
                    pair_id=pair.id,
                    subscription_id=sub.id,
                    period_end=sub.period_end.isoformat(),
                )
                
                # Send notifications if requested (in separate try-except)
                if send_notifications:
                    try:
                        lock_service = worker_context.lock_service
                        dunning_key = f"dunning_notification:{pair.id}:{today.isoformat()}"
                        can_send = await lock_service.set_key_if_not_exists(
                            dunning_key,
                            "1",
                            86400,
                        )
                        if not can_send:
                            logger.debug(
                                "Dunning notification already sent today",
                                pair_id=pair.id,
                            )
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
                        
                        # Send notifications using NotificationBuilder
                        messenger = worker_context.messenger
                        notification_builder = worker_context.notification_builder
                        
                        label_for_a = format_partner_label(
                            partner_nickname=pairs_repo.get_my_nickname_for_partner(pair, user_a.id),
                            partner_username=user_b.username,
                        )
                        label_for_b = format_partner_label(
                            partner_nickname=pairs_repo.get_my_nickname_for_partner(pair, user_b.id),
                            partner_username=user_a.username,
                        )
                        dunning_text_a, keyboard = await notification_builder.build_dunning_notification_message(
                            partner_label=label_for_a,
                            pair_id=pair.id,
                        )
                        dunning_text_b, _keyboard_b = await notification_builder.build_dunning_notification_message(
                            partner_label=label_for_b,
                            pair_id=pair.id,
                        )
                        
                        await messenger.send_message(
                            chat_id=user_a.tg_id,
                            text=dunning_text_a,
                            reply_markup=keyboard,
                        )
                        await messenger.send_message(
                            chat_id=user_b.tg_id,
                            text=dunning_text_b,
                            reply_markup=keyboard,
                        )
                        
                        logger.info("Dunning notification sent", pair_id=pair.id)
                    except Exception as notification_error:
                        # Log error but don't fail the task - status is already updated
                        logger.error(
                            "Error sending dunning notification (status already updated)",
                            pair_id=pair.id,
                            error=str(notification_error),
                            exc_info=True,
                        )
                
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
        pairs_repo = PairsRepository(session)
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
        
        # Reserve notification slot atomically to avoid duplicates
        days_since_expiry = (today - subscription.period_end).days
        if days_since_expiry <= 3:
            past_due_notification_key = (
                f"past_due_notification_{pic_type}:{pair.id}:{today.isoformat()}"
            )
            reserved = await lock_service.set_key_if_not_exists(
                past_due_notification_key,
                "1",
                86400,
            )
            if not reserved:
                return
        else:
            last_notification_key = f"past_due_last_notification_{pic_type}:{pair.id}"
            reserved = await lock_service.set_key_if_not_exists(
                last_notification_key,
                today.isoformat(),
                7 * 86400,
            )
            if not reserved:
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
        
        label_for_a = format_partner_label(
            partner_nickname=pairs_repo.get_my_nickname_for_partner(pair, user_a.id),
            partner_username=user_b.username,
        )
        label_for_b = format_partner_label(
            partner_nickname=pairs_repo.get_my_nickname_for_partner(pair, user_b.id),
            partner_username=user_a.username,
        )
        notification_text_a, reply_markup = await notification_builder.build_past_due_notification_message(
            include_button=True,
            partner_label=label_for_a,
            pair_id=pair.id,
        )
        notification_text_b, _reply_markup_b = await notification_builder.build_past_due_notification_message(
            include_button=True,
            partner_label=label_for_b,
            pair_id=pair.id,
        )
        
        await messenger.send_message(
            chat_id=user_a.tg_id,
            text=notification_text_a,
            reply_markup=reply_markup,
        )
        await messenger.send_message(
            chat_id=user_b.tg_id,
            text=notification_text_b,
            reply_markup=reply_markup,
        )
        
        # Update subscription
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

