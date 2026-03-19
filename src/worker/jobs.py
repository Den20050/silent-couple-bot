"""Arq cron jobs - main entry point."""

from typing import Any

from arq import cron
from arq.connections import RedisSettings

from src.core.config import settings
from src.core.logger import get_logger
from src.worker.di.context import WorkerContext, create_worker_context
from src.worker.tasks.morning import morning_sender as morning_sender_task
from src.worker.tasks.evening import evening_sender as evening_sender_task
from src.worker.tasks.past_due import dunning_notifications as dunning_notifications_task
from src.worker.tasks.reminders import (
    send_recipient_reminder as send_recipient_reminder_task,
    send_initiator_warning as send_initiator_warning_task,
)
from src.worker.tasks.cleanup import (
    cleanup_old_data as cleanup_old_data_task,
    cleanup_old_messages as cleanup_old_messages_task,
)
# from src.worker.tasks.summary import send_week_summary as send_week_summary_task
from src.worker.tasks.nudges import send_share_nudge as send_share_nudge_task
from src.worker.tasks.renewal import send_renewal_reminders as send_renewal_reminders_task

logger = get_logger(__name__)

# Global worker context (initialized on first use)
_global_worker_context: WorkerContext | None = None
_context_lock = None


async def get_worker_context() -> WorkerContext:
    """Get or create global worker context for worker jobs.
    
    Note: This function is async because bootstrap() is async.
    It should be called from within an async context (Arq worker jobs).
    """
    global _global_worker_context, _context_lock
    if _context_lock is None:
        import asyncio
        _context_lock = asyncio.Lock()
    
    if _global_worker_context is None:
        async with _context_lock:
            # Double-check pattern
            if _global_worker_context is None:
                from src.core.bootstrap import bootstrap
                container = await bootstrap()
                
                # Create worker context from container
                _global_worker_context = create_worker_context(
                    settings=container.settings,
                    session_factory=container.session_factory,
                    redis=container.redis,
                    messenger=container.telegram_messenger,
                    bot_provider=container.bot_provider,
                )
    return _global_worker_context


# Wrapper functions for Arq (Arq doesn't support DI directly)
async def morning_sender(ctx: dict[str, Any]) -> None:
    """Wrapper for morning sender task."""
    worker_context = await get_worker_context()
    await morning_sender_task(ctx, worker_context)


async def evening_sender(ctx: dict[str, Any]) -> None:
    """Wrapper for evening sender task."""
    worker_context = await get_worker_context()
    await evening_sender_task(ctx, worker_context)


async def dunning_notifications(ctx: dict[str, Any]) -> None:
    """Wrapper for dunning notifications task."""
    worker_context = await get_worker_context()
    await dunning_notifications_task(ctx, worker_context)


async def cleanup_old_data(ctx: dict[str, Any]) -> None:
    """Wrapper for cleanup old data task."""
    worker_context = await get_worker_context()
    await cleanup_old_data_task(ctx, worker_context)


async def send_recipient_reminder(
    ctx: dict[str, Any],
    pair_id: int,
    recipient_tg_id: int,
    pic_type: str,
    hours: int,
) -> None:
    """Wrapper for send recipient reminder task."""
    worker_context = await get_worker_context()
    await send_recipient_reminder_task(
        ctx,
        pair_id,
        recipient_tg_id,
        pic_type,
        hours,
        worker_context,
    )


async def send_initiator_warning(
    ctx: dict[str, Any],
    pair_id: int,
    initiator_tg_id: int,
    recipient_user_id: int,
    pic_type: str,
    hours: int,
) -> None:
    """Wrapper for send initiator warning task."""
    worker_context = await get_worker_context()
    await send_initiator_warning_task(
        ctx,
        pair_id,
        initiator_tg_id,
        recipient_user_id,
        pic_type,
        hours,
        worker_context,
    )


# async def send_week_summary(ctx: dict[str, Any]) -> None:
#     """Wrapper for send week summary task."""
#     worker_context = await get_worker_context()
#     await send_week_summary_task(ctx, worker_context)


async def send_share_nudge(ctx: dict[str, Any]) -> None:
    """Wrapper for send share nudge task."""
    worker_context = await get_worker_context()
    await send_share_nudge_task(ctx, worker_context)


async def cleanup_old_messages(ctx: dict[str, Any]) -> None:
    """Wrapper for cleanup old messages task."""
    worker_context = await get_worker_context()
    await cleanup_old_messages_task(ctx, worker_context)


async def send_renewal_reminders(ctx: dict[str, Any]) -> None:
    """Wrapper for send renewal reminders task."""
    worker_context = await get_worker_context()
    await send_renewal_reminders_task(ctx, worker_context)


class WorkerSettings:
    """Arq worker settings."""

    # Configure Redis with increased timeouts for SSH tunnel stability
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    redis_settings.conn_timeout = 10  # Connection timeout in seconds
    
    functions = [
        morning_sender,
        evening_sender,
        cleanup_old_data,
        dunning_notifications,
        send_recipient_reminder,
        send_initiator_warning,
        # send_week_summary,  # Disabled: weekly summary notifications
        send_share_nudge,
        cleanup_old_messages,
        send_renewal_reminders,
    ]
    cron_jobs = [
        cron(morning_sender, minute=None),  # Every minute
        cron(evening_sender, minute=None),  # Every minute
        cron(cleanup_old_data, hour=3, minute=0),  # 03:00 UTC
        cron(dunning_notifications, hour=None, minute=0),  # Every hour - check expired subscriptions
        # cron(send_week_summary, hour=0, minute=0),  # 00:00 UTC - Disabled: weekly summary
        cron(send_share_nudge, hour=14, minute=0),  # 14:00 UTC
        cron(cleanup_old_messages, hour=None, minute=30),  # Every hour at :30
        cron(send_renewal_reminders, hour=None, minute=0),  # Every hour
    ]
