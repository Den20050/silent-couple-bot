"""Service for sending reminders and warnings."""

from datetime import date

from src.core.config import settings
from src.core.logger import get_logger
from src.core.messages import get_message
from src.worker.di.context import WorkerContext
from src.worker.services.reminder_finder import ReminderCandidate
from src.services.messaging.active_action_message import activate_message
from src.services.messaging.partner_label import format_partner_label

logger = get_logger(__name__)


class ReminderSender:
    """Service for sending reminders to recipients."""
    
    def __init__(
        self,
        worker_context: WorkerContext,
    ):
        """Initialize reminder sender.
        
        Args:
            worker_context: Worker context with dependencies
        """
        self._worker_context = worker_context
        self._messenger = worker_context.messenger
        self._notification_builder = worker_context.notification_builder
    
    async def send_reminder(
        self,
        candidate: ReminderCandidate,
        reminder_key: str,
        lock_service,
    ) -> None:
        """Send reminder to recipient.
        
        Args:
            candidate: ReminderCandidate with all necessary data
            reminder_key: Redis key for tracking
            lock_service: LockService instance
        """
        # Build reminder message using NotificationBuilder
        # candidate.initiator already contains the initiator user
        # Include initiator label so reminders are understandable for multi-pair users.
        # Prefer nickname (what recipient calls initiator), otherwise @username.
        nickname_for_initiator = (
            candidate.pair.nickname_a
            if candidate.pair.uid_a == candidate.recipient.id
            else candidate.pair.nickname_b
            if candidate.pair.uid_b == candidate.recipient.id
            else None
        )
        initiator_label = format_partner_label(
            partner_nickname=nickname_for_initiator,
            partner_username=candidate.initiator.username,
        )

        reminder_text, reply_markup = await self._notification_builder.build_reminder_message(
            pair_mode=candidate.pair.mode,
            pic_type=candidate.pic_type,
            pair_id=candidate.pair.id,
            initiator_tg_id=candidate.initiator.tg_id,
            target_day=candidate.target_day,
            initiator_label=initiator_label,
        )
        
        msg = await self._messenger.send_message(
            chat_id=candidate.recipient.tg_id,
            text=reminder_text,
            reply_markup=reply_markup,
        )

        # Make this reminder the only active interactive message (best-effort).
        await activate_message(
            redis=self._worker_context.redis,
            messenger=self._messenger,
            tg_id=candidate.recipient.tg_id,
            message_id=msg.message_id,
        )
        
        # Mark reminder as sent
        await lock_service.set_key_with_ttl(
            reminder_key, "1", settings.reminder_ttl_hours * 3600
        )
        
        logger.info(
            "Recipient reminder sent",
            pair_id=candidate.pair.id,
            recipient_tg_id=candidate.recipient.tg_id,
            pic_type=candidate.pic_type,
        )


class WarningSender:
    """Service for sending warnings to initiators."""
    
    def __init__(
        self,
        worker_context: WorkerContext,
    ):
        """Initialize warning sender.
        
        Args:
            worker_context: Worker context with dependencies
        """
        self._worker_context = worker_context
        self._messenger = worker_context.messenger
        self._notification_builder = worker_context.notification_builder
    
    async def send_warning(
        self,
        candidate: ReminderCandidate,
        hours: int,
        warning_key: str,
        lock_service,
    ) -> None:
        """Send warning to initiator.
        
        Args:
            candidate: ReminderCandidate with all necessary data
            hours: Hours since picture was sent
            warning_key: Redis key for tracking
            lock_service: LockService instance
        """
        # Prepare message with username or fallback
        recipient_name = (
            f"@{candidate.recipient.username}"
            if candidate.recipient.username
            else get_message("WORKER_RECIPIENT_FALLBACK")
        )
        
        # Build warning message using NotificationBuilder
        warning_message, reply_markup = await self._notification_builder.build_warning_message(
            pair_mode=candidate.pair.mode,
            recipient_name=recipient_name,
            hours=hours,
            pair_id=candidate.pair.id,
            target_day=candidate.target_day,
            pic_type=candidate.pic_type,
        )
        
        await self._messenger.send_message(
            chat_id=candidate.initiator.tg_id,
            text=warning_message,
            reply_markup=reply_markup,
        )
        
        # Note: Last warning time is tracked by caller using set_last_warning_time
        
        logger.info(
            "Initiator warning sent",
            pair_id=candidate.pair.id,
            initiator_tg_id=candidate.initiator.tg_id,
            recipient_tg_id=candidate.recipient.tg_id,
            pic_type=candidate.pic_type,
            hours=hours,
        )

