"""State checking utilities for worker tasks."""

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository

logger = get_logger(__name__)


async def should_send_reminder(
    session: AsyncSession,
    pair_id: int,
    pic_type: str,
    hours_after_send: int,
    daily_state_repo: DailyStateRepository,
) -> tuple[bool, Optional[date]]:
    """Check if reminder should be sent for unanswered picture.
    
    Args:
        session: Database session
        pair_id: Pair ID
        pic_type: Picture type ("morning" or "evening")
        hours_after_send: Hours after picture was sent
        daily_state_repo: DailyStateRepository instance
        
    Returns:
        Tuple of (should_send: bool, target_day: Optional[date])
    """
    # Get current state for the pair
    # We need to check all days that might have unanswered pictures
    today = date.today()
    
    # Check today and yesterday (for reminders that might be for previous day)
    for check_day in [today, today - timedelta(days=1)]:
        current_state = await daily_state_repo.get_by_pair_and_day(
            pair_id,
            check_day,
        )
        
        if not current_state:
            continue
        
        # Check if picture was sent and not answered
        if pic_type == "morning":
            if current_state.morning_initiator is None:
                continue
            if current_state.morning_responded_at is not None:
                continue
            sent_at = current_state.morning_sent_at
        else:  # evening
            if current_state.evening_initiator is None:
                continue
            if current_state.evening_responded_at is not None:
                continue
            sent_at = current_state.evening_sent_at
        
        if not sent_at:
            continue
        
        # Check if enough hours have passed
        now_utc = datetime.utcnow()
        hours_passed = (now_utc - sent_at).total_seconds() / 3600
        
        if hours_passed < hours_after_send - 0.5:  # Allow 30 min tolerance
            continue
        
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
                pair_id=pair_id,
                check_day=str(check_day),
                pic_type=pic_type,
            )
            return False, None

        # Check if recipient has already responded to the other picture type
        if pic_type == "morning":
            if current_state.evening_responded_at is not None:
                logger.info(
                    "Skipping morning reminder: recipient already responded to evening",
                    pair_id=pair_id,
                    check_day=str(check_day),
                )
                return False, None
        else:  # evening
            if current_state.morning_responded_at is not None:
                logger.info(
                    "Skipping evening reminder: recipient already responded to morning",
                    pair_id=pair_id,
                    check_day=str(check_day),
                )
                return False, None
        
        # Check if any picture was initiated on the next day (new cycle started)
        next_day = check_day + timedelta(days=1)
        next_day_state = await daily_state_repo.get_by_pair_and_day(
            pair_id,
            next_day,
        )
        
        if next_day_state and (
            next_day_state.morning_initiator is not None
            or next_day_state.evening_initiator is not None
        ):
            logger.info(
                "Skipping reminder: newer wish exists on next day",
                pair_id=pair_id,
                check_day=str(check_day),
                next_day=str(next_day),
            )
            return False, None
        
        return True, check_day
    
    return False, None


async def check_past_due_notification_needed(
    session: AsyncSession,
    pair_id: int,
    today: date,
    subscription,
    lock_service,
    pic_type: str = "morning",
) -> bool:
    """Check if past due notification should be sent.
    
    Args:
        session: Database session
        pair_id: Pair ID
        today: Current date
        subscription: Subscription object
        lock_service: LockService instance
        
    Returns:
        True if notification should be sent, False otherwise
    """
    if not subscription:
        return False

    if pic_type == "evening":
        return False
    
    days_since_expiry = (today - subscription.period_end).days
    
    if days_since_expiry <= 3:
        # First 3 days: check if already sent today for this pic_type
        # We allow both morning and evening notifications in the same day
        past_due_notification_key = (
            f"past_due_notification_{pic_type}:{pair_id}:{today.isoformat()}"
        )
        notification_already_sent = await lock_service.check_key_exists(
            past_due_notification_key
        )
        if notification_already_sent:
            return False
        
        # Fallback to database check if Redis is not available
        # Note: We don't check last_past_due_notification_date here because
        # we want to allow both morning and evening notifications in the same day
        
        return True
    else:
        # After 3 days: check if 7 days passed since last notification for this pic_type
        # Use separate keys for morning and evening to allow both in the same day
        last_notification_key = f"past_due_last_notification_{pic_type}:{pair_id}"
        last_notification_date_str = await lock_service.get_key(
            last_notification_key
        )
        
        if last_notification_date_str:
            try:
                last_notification_date = date.fromisoformat(last_notification_date_str)
                days_since_last = (today - last_notification_date).days
                if days_since_last < 7:
                    return False
            except (ValueError, TypeError):
                # Invalid date format, fall through to allow sending
                pass
        
        # Fallback to database check if Redis is not available
        # Check if 7 days passed since last notification (any notification)
        # Note: This is a fallback - ideally Redis should be available
        if subscription.last_past_due_notification_date:
            days_since_last = (
                today - subscription.last_past_due_notification_date
            ).days
            # If less than 7 days passed, don't send
            # But this doesn't distinguish between morning and evening,
            # so we prefer Redis check above
            if days_since_last < 7:
                return False
        
        return True

