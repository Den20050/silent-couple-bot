"""Use case for scheduling reminder tasks."""

from datetime import timedelta

from arq import create_pool
from arq.connections import RedisSettings

from src.core.config import Settings
from src.core.logger import get_logger

logger = get_logger(__name__)


async def schedule_reminder_tasks(
    pair_id: int,
    initiator_tg_id: int,
    recipient_tg_id: int,
    recipient_user_id: int,
    pic_type: str,
    settings: Settings,
) -> None:
    """Schedule reminder tasks for unanswered wishes.
    
    Args:
        pair_id: Pair ID
        initiator_tg_id: Telegram ID of the initiator
        recipient_tg_id: Telegram ID of the recipient
        recipient_user_id: User ID of the recipient
        pic_type: Picture type ("morning" or "evening")
        settings: Application settings
    """
    try:
        redis_url = settings.redis_url
        arq_redis = await create_pool(RedisSettings.from_dsn(redis_url))
        
        # Schedule recipient reminders
        for reminder_hours in settings.get_reminder_hours():
            await arq_redis.enqueue_job(
                "send_recipient_reminder",
                pair_id=pair_id,
                recipient_tg_id=recipient_tg_id,
                pic_type=pic_type,
                hours=reminder_hours,
                _defer_by=timedelta(hours=reminder_hours),
            )
        
        # Schedule initiator warnings from min hours, then with interval, ensuring 24h is included.
        warning_hours_set = set(
            range(settings.warning_min_hours, 25, settings.warning_interval_hours)
        )
        if 24 >= settings.warning_min_hours:
            warning_hours_set.add(24)

        for warning_hours in sorted(warning_hours_set):
            await arq_redis.enqueue_job(
                "send_initiator_warning",
                pair_id=pair_id,
                initiator_tg_id=initiator_tg_id,
                recipient_user_id=recipient_user_id,
                pic_type=pic_type,
                hours=warning_hours,
                _defer_by=timedelta(hours=warning_hours),
            )
        
        await arq_redis.close()
        
        logger.info(
            "Scheduled reminder tasks",
            pair_id=pair_id,
            pic_type=pic_type,
            initiator_tg_id=initiator_tg_id,
            recipient_id=recipient_user_id,
        )
    except Exception as e:
        logger.error(
            "Failed to schedule reminder tasks",
            pair_id=pair_id,
            error=str(e),
            exc_info=True,
        )
        # Don't fail the whole operation if scheduling fails

