"""Cleanup tasks for old data and messages."""

from datetime import datetime, timedelta
from typing import Any

from src.core.constants import DAILY_STATE_RETENTION_DAYS
from src.core.logger import get_logger
from src.db.repositories.daily_state import DailyStateRepository
from src.worker.di.context import WorkerContext

logger = get_logger(__name__)


async def cleanup_old_data(
    ctx: dict[str, Any],
    worker_context: WorkerContext,
) -> None:
    """Delete old daily_state records older than retention period.
    
    Args:
        ctx: Arq context
        worker_context: Worker context with dependencies
    """
    try:
        # Ensure bot is initialized (needed for messenger)
        await worker_context.ensure_bot_initialized()
        
        async with worker_context.session_factory() as session:
            daily_state_repo = DailyStateRepository(session)
            
            deleted_count = await daily_state_repo.cleanup_old()
            await session.commit()
            
            logger.info(
                "Old daily_state records cleaned up",
                deleted_count=deleted_count,
                retention_days=DAILY_STATE_RETENTION_DAYS,
            )
    finally:
        pass


async def cleanup_old_messages(
    ctx: dict[str, Any],
    worker_context: WorkerContext,
) -> None:
    """Delete old bot messages older than 48 hours.
    
    Args:
        ctx: Arq context
        worker_context: Worker context with dependencies
    """
    try:
        # Ensure bot is initialized (needed for messenger)
        await worker_context.ensure_bot_initialized()
        
        messenger = worker_context.messenger
        
        async with worker_context.session_factory() as session:
            from src.db.repositories.bot_messages import BotMessagesRepository
            bot_messages_repo = BotMessagesRepository(session)
            
            # Find messages older than 48 hours
            old_messages = await bot_messages_repo.get_old_messages(hours=48)
            
            logger.info(
                "Found old messages to delete",
                count=len(old_messages),
            )
            
            deleted_count = 0
            failed_count = 0
            
            for message_record in old_messages:
                try:
                    # Try to delete message via Telegram API
                    success = await messenger.delete_message(
                        chat_id=message_record.chat_id,
                        message_id=message_record.message_id,
                    )
                    
                    if success:
                        # Delete record from database
                        await bot_messages_repo.delete_by_ids([message_record.id])
                        deleted_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    # Message might already be deleted by user
                    # Delete record anyway
                    try:
                        await bot_messages_repo.delete_by_ids([message_record.id])
                        deleted_count += 1
                    except Exception:
                        failed_count += 1
                        logger.warning(
                            "Failed to delete message record",
                            message_id=message_record.id,
                            error=str(e),
                        )
            
            await session.commit()
            
            logger.info(
                "Old messages cleaned up",
                deleted_count=deleted_count,
                failed_count=failed_count,
                total_found=len(old_messages),
            )
    finally:
        pass

