"""Nudge tasks for user engagement."""

from datetime import date, timedelta
from typing import Any, Optional

from src.core.config import settings
from src.core.constants import PairStatus
from src.core.logger import get_logger
from src.db.repositories.pairs import PairsRepository
from src.worker.di.context import WorkerContext

logger = get_logger(__name__)


async def send_share_nudge(
    ctx: dict[str, Any],
    worker_context: WorkerContext,
) -> None:
    """Send nudge to share bot with others.
    
    Sends one message per user, regardless of how many pairs they have.
    
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
            
            # Get active pairs
            pairs = await pairs_repo.get_active_pairs()
            logger.info("Active pairs found for share nudge", count=len(pairs))
            
            # Collect unique users and their first pair mode
            # Key: user_id, Value: (tg_id, pair_mode)
            users_to_notify: dict[int, tuple[int, str]] = {}
            
            for pair in pairs:
                # Add user A if not already added
                if pair.uid_a not in users_to_notify:
                    users_to_notify[pair.uid_a] = (None, pair.mode)  # tg_id will be fetched later
                # Add user B if not already added
                if pair.uid_b not in users_to_notify:
                    users_to_notify[pair.uid_b] = (None, pair.mode)  # tg_id will be fetched later
            
            # Fetch user tg_ids
            from sqlalchemy import select
            from src.db.models import User
            
            for user_id in list(users_to_notify.keys()):
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one()
                pair_mode = users_to_notify[user_id][1]
                users_to_notify[user_id] = (user.tg_id, pair_mode)
            
            sent_count = 0
            skipped_count = 0
            today = date.today()
            
            # Send one message per user
            for user_id, (tg_id, pair_mode) in users_to_notify.items():
                try:
                    # Check if nudge already sent today for this user
                    nudge_key = f"share_nudge_sent:user:{tg_id}:{today.isoformat()}"
                    
                    already_sent = await lock_service.check_key_exists(nudge_key)
                    if already_sent:
                        skipped_count += 1
                        continue
                    
                    # Send nudge using NotificationBuilder
                    messenger = worker_context.messenger
                    notification_builder = worker_context.notification_builder
                    
                    nudge_text, share_keyboard = await notification_builder.build_share_nudge_message(
                        pair_mode=pair_mode,
                    )
                    
                    await messenger.send_message(
                        chat_id=tg_id,
                        text=nudge_text,
                        reply_markup=share_keyboard,
                    )
                    
                    # Mark nudge as sent for this user
                    await lock_service.set_key_with_ttl(
                        nudge_key,
                        "1",
                        settings.nudge_ttl_hours * 3600,
                    )
                    
                    sent_count += 1
                except Exception as e:
                    logger.error(
                        "Error sending share nudge",
                        user_id=user_id,
                        tg_id=tg_id,
                        error=str(e),
                        exc_info=True,
                    )
                    continue
            
            logger.info(
                "Share nudge completed",
                sent_count=sent_count,
                skipped_count=skipped_count,
                total_users=len(users_to_notify),
                total_pairs=len(pairs),
            )
    finally:
        await worker_context.close_bot()
        await lock_service.close()

