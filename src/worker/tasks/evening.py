"""Evening sender task."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from src.core.logger import get_logger
from src.db.models import User
from src.worker.di.context import WorkerContext

logger = get_logger(__name__)


async def evening_sender(ctx: dict[str, Any], worker_context: WorkerContext) -> None:
    """Send evening pictures within configured time window.
    
    Args:
        ctx: Arq context
        worker_context: Worker context with dependencies
    """
    task_name = "evening_sender"
    
    # Acquire lock using LockService from context
    lock_service = worker_context.lock_service
    lock_acquired = await lock_service.acquire_task_lock(task_name)
    if not lock_acquired:
        logger.debug("Task already running, skipping", task=task_name)
        return
    
    try:
        # Ensure bot is initialized
        await worker_context.ensure_bot_initialized()
        
        now_utc = datetime.utcnow()
        today = date.today()
        
        async with worker_context.session_factory() as session:
            scheduler = worker_context.create_pair_scheduler(session)
            
            from src.db.repositories.pairs import PairsRepository
            from src.db.repositories.subscriptions import SubscriptionsRepository
            pairs_repo = PairsRepository(session)
            subs_repo = SubscriptionsRepository(session)
            
            # Get active pairs
            pairs = await pairs_repo.get_active_pairs()
            logger.info("Active pairs found", count=len(pairs))
            
            # Get past_due pairs for subscription notifications
            past_due_pairs = await pairs_repo.get_past_due_pairs()
            logger.info("Past due pairs found", count=len(past_due_pairs))
            
            sent_count = 0
            
            # Process active pairs - send wishes
            for pair in pairs:
                try:
                    # Get users
                    user_a_result = await session.execute(
                        select(User).where(User.id == pair.uid_a)
                    )
                    user_a = user_a_result.scalar_one()
                    
                    user_b_result = await session.execute(
                        select(User).where(User.id == pair.uid_b)
                    )
                    user_b = user_b_result.scalar_one()
                    
                    # Try to send wish
                    success = await scheduler.send_wish_for_pair(
                        pair=pair,
                        user_a=user_a,
                        user_b=user_b,
                        pic_type="evening",
                        today=today,
                        now_utc=now_utc,
                    )
                    
                    if success:
                        sent_count += 1
                        await session.commit()
                except Exception as e:
                    logger.error(
                        "Error sending evening wish",
                        pair_id=pair.id,
                        error=str(e),
                        exc_info=True,
                    )
                    await session.rollback()
                    continue
            
            # Process past_due pairs - send subscription notifications instead of wishes
            from src.worker.tasks.past_due import send_past_due_notification
            
            for pair in past_due_pairs:
                try:
                    # Get subscription
                    subscription = await subs_repo.get_by_pair_id(pair.id)
                    if not subscription:
                        continue
                    
                    # Send past due notification if needed
                    # This will check if morning notification was already sent today
                    # and skip if it was (to avoid duplicate notifications)
                    await send_past_due_notification(
                        worker_context=worker_context,
                        pair=pair,
                        subscription=subscription,
                        today=today,
                        pic_type="evening",
                    )
                except Exception as e:
                    logger.error(
                        "Error sending past due notification",
                        pair_id=pair.id,
                        error=str(e),
                        exc_info=True,
                    )
                    continue
            
            logger.info("Evening sender completed", sent_count=sent_count)
    finally:
        await worker_context.close_bot()
        await lock_service.close()

