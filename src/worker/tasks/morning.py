"""Morning sender task."""

from collections import Counter
from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from src.core.config import settings
from src.core.logger import get_logger
from src.db.models import User
from src.worker.di.context import WorkerContext

logger = get_logger(__name__)


def _mask_db_url(url: str) -> str:
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    _creds, tail = rest.split("@", 1)
    return f"{scheme}://***@{tail}"


async def morning_sender(ctx: dict[str, Any], worker_context: WorkerContext) -> None:
    """Send morning pictures within configured time window.
    
    Args:
        ctx: Arq context
        worker_context: Worker context with dependencies
    """
    task_name = "morning_sender"
    
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
        logger.info(
            "Morning sender tick",
            now_utc=now_utc.isoformat(),
            today=str(today),
            database_url=_mask_db_url(settings.database_url),
        )
        
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
            reasons: Counter[str] = Counter()
            
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
                    success, reason = await scheduler.send_wish_for_pair(
                        pair=pair,
                        user_a=user_a,
                        user_b=user_b,
                        pic_type="morning",
                        today=today,
                        now_utc=now_utc,
                    )
                    reasons[reason] += 1
                    
                    if success:
                        sent_count += 1
                        await session.commit()
                except Exception as e:
                    logger.error(
                        "Error sending morning wish",
                        pair_id=pair.id,
                        error=str(e),
                        exc_info=True,
                    )
                    await session.rollback()
                    continue
            
            # Process past_due pairs - send subscription notifications
            from src.worker.tasks.past_due import send_past_due_notification
            
            for pair in past_due_pairs:
                try:
                    # Get subscription
                    subscription = await subs_repo.get_by_pair_id(pair.id)
                    if not subscription:
                        continue
                    
                    # Send past due notification if needed
                    await send_past_due_notification(
                        worker_context=worker_context,
                        pair=pair,
                        subscription=subscription,
                        today=today,
                        pic_type="morning",
                    )
                except Exception as e:
                    logger.error(
                        "Error sending past due notification",
                        pair_id=pair.id,
                        error=str(e),
                        exc_info=True,
                    )
                    continue
            
            logger.info(
                "Morning sender completed",
                sent_count=sent_count,
                reasons=dict(reasons),
            )
    finally:
        await worker_context.close_bot()
        await lock_service.close()

