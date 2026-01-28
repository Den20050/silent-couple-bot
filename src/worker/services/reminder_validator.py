"""Service for validating reminder conditions."""

from datetime import timedelta

from src.core.logger import get_logger
from src.db.repositories.daily_state import DailyStateRepository
from src.worker.services.reminder_finder import ReminderCandidate

logger = get_logger(__name__)


class ReminderValidator:
    """Service for validating reminder conditions."""
    
    def __init__(
        self,
        daily_state_repo: DailyStateRepository,
    ):
        """Initialize reminder validator.
        
        Args:
            daily_state_repo: DailyStateRepository instance
        """
        self._daily_state_repo = daily_state_repo
    
    async def should_send_reminder(
        self,
        candidate: ReminderCandidate,
    ) -> bool:
        """Check if reminder should be sent for candidate.
        
        Args:
            candidate: ReminderCandidate to validate
            
        Returns:
            True if reminder should be sent, False otherwise
        """
        pic_type = candidate.pic_type
        current_state = candidate.daily_state
        
        sent_at = (
            current_state.morning_sent_at
            if pic_type == "morning"
            else current_state.evening_sent_at
        )
        other_sent_at = (
            current_state.evening_sent_at
            if pic_type == "morning"
            else current_state.morning_sent_at
        )

        # If a newer wish was sent on the same day, ignore older one.
        if sent_at and other_sent_at and other_sent_at > sent_at:
            logger.info(
                "Skipping reminder: newer wish sent on same day",
                pair_id=candidate.pair.id,
                target_day=str(candidate.target_day),
                pic_type=pic_type,
            )
            return False

        # Check if recipient has already responded to the other picture type
        if pic_type == "morning":
            if current_state.evening_responded_at is not None:
                logger.info(
                    "Skipping morning reminder: recipient already responded to evening",
                    pair_id=candidate.pair.id,
                    target_day=str(candidate.target_day),
                )
                return False
        else:  # evening
            if current_state.morning_responded_at is not None:
                logger.info(
                    "Skipping evening reminder: recipient already responded to morning",
                    pair_id=candidate.pair.id,
                    target_day=str(candidate.target_day),
                )
                return False
        
        # Check if any picture was initiated on the next day (new cycle started)
        next_day = candidate.target_day + timedelta(days=1)
        next_day_state = await self._daily_state_repo.get_by_pair_and_day(
            candidate.pair.id,
            next_day,
        )
        
        if next_day_state and (
            next_day_state.morning_initiator is not None
            or next_day_state.evening_initiator is not None
        ):
            logger.info(
                "Skipping reminder: newer wish exists on next day",
                pair_id=candidate.pair.id,
                target_day=str(candidate.target_day),
                next_day=str(next_day),
            )
            return False
        
        return True
    
    async def should_send_warning(
        self,
        candidate: ReminderCandidate,
    ) -> bool:
        """Check if warning should be sent for candidate.
        
        Args:
            candidate: ReminderCandidate to validate
            
        Returns:
            True if warning should be sent, False otherwise
        """
        # Same validation logic as reminders
        return await self.should_send_reminder(candidate)

