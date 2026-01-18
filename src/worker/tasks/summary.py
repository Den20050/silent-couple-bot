"""Summary tasks for weekly statistics."""

from datetime import date, timedelta
from typing import Any, Optional

from src.core.config import settings
from src.core.constants import PairStatus
from src.core.logger import get_logger
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.worker.di.context import WorkerContext

logger = get_logger(__name__)


async def send_week_summary(
    ctx: dict[str, Any],
    worker_context: WorkerContext,
) -> None:
    """Send weekly summary to active pairs.
    
    Args:
        ctx: Arq context
        worker_context: Worker context with dependencies
    """
    lock_service = worker_context.lock_service
    try:
        # Ensure bot is initialized
        await worker_context.ensure_bot_initialized()
        
        async with worker_context.session_factory() as session:
            pairs_repo = PairsRepository(session)
            daily_state_repo = DailyStateRepository(session)
            
            # Get active pairs
            pairs = await pairs_repo.get_active_pairs()
            logger.info("Active pairs found for week summary", count=len(pairs))
            
            sent_count = 0
            skipped_count = 0
            
            for pair in pairs:
                try:
                    # Check if summary already sent this week
                    today = date.today()
                    week_start = today - timedelta(days=today.weekday())
                    summary_key = f"week_summary_sent:{pair.id}:{week_start.isoformat()}"
                    
                    already_sent = await worker_context.lock_service.check_key_exists(summary_key)
                    if already_sent:
                        skipped_count += 1
                        continue
                    
                    # Get week stats
                    stats = await daily_state_repo.get_week_stats(pair.id)
                    days_count = stats.get("days_count", 0)
                    
                    # Get users
                    from sqlalchemy import select
                    from src.db.models import User
                    user_a_result = await session.execute(
                        select(User).where(User.id == pair.uid_a)
                    )
                    user_a = user_a_result.scalar_one()
                    user_b_result = await session.execute(
                        select(User).where(User.id == pair.uid_b)
                    )
                    user_b = user_b_result.scalar_one()
                    
                    # Send summary using NotificationBuilder
                    messenger = worker_context.messenger
                    notification_builder = worker_context.notification_builder

                    # Include partner nickname only when partner has no username.
                    nickname_for_a = (
                        pairs_repo.get_my_nickname_for_partner(pair, user_a.id)
                        if not user_b.username
                        else None
                    )
                    nickname_for_b = (
                        pairs_repo.get_my_nickname_for_partner(pair, user_b.id)
                        if not user_a.username
                        else None
                    )

                    summary_text_a = await notification_builder.build_week_summary_message(
                        pair_mode=pair.mode,
                        days_count=days_count,
                        partner_nickname=nickname_for_a,
                    )
                    summary_text_b = await notification_builder.build_week_summary_message(
                        pair_mode=pair.mode,
                        days_count=days_count,
                        partner_nickname=nickname_for_b,
                    )
                    
                    await messenger.send_message(chat_id=user_a.tg_id, text=summary_text_a)
                    await messenger.send_message(chat_id=user_b.tg_id, text=summary_text_b)
                    
                    # Mark summary as sent
                    await worker_context.lock_service.set_key_with_ttl(
                        summary_key,
                        "1",
                        settings.summary_ttl_days * 24 * 3600,
                    )
                    
                    sent_count += 1
                except Exception as e:
                    logger.error(
                        "Error sending week summary",
                        pair_id=pair.id,
                        error=str(e),
                        exc_info=True,
                    )
                    continue
            
            logger.info(
                "Week summary completed",
                sent_count=sent_count,
                skipped_count=skipped_count,
                total_pairs=len(pairs),
            )
    finally:
        await worker_context.close_bot()
        await lock_service.close()

