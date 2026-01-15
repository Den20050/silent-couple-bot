"""Pair scheduling service for sending wishes and reminders."""

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PicType, PairStatus
from src.core.config import settings
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.image import ImageService
from src.services.messaging.caption_service import CaptionService
from src.core.protocols.messenger import MessengerProtocol
from src.worker.services.time_window_service import TimeWindowService
from src.worker.services.lock_service import LockService

logger = get_logger(__name__)


class PairScheduler:
    """Service for scheduling and sending pair wishes."""
    
    def __init__(
        self,
        session: AsyncSession,
        telegram_messenger: MessengerProtocol,
        lock_service: LockService,
    ) -> None:
        """Initialize pair scheduler.
        
        Args:
            session: Database session
            telegram_messenger: Telegram messenger instance
            lock_service: LockService instance for Redis operations
        """
        self.session = session
        self.telegram_messenger = telegram_messenger
        self.lock_service = lock_service
        self.pairs_repo = PairsRepository(session)
        self.daily_state_repo = DailyStateRepository(session)
        self.users_repo = UsersRepository(session)
        self.image_service = ImageService(session)
        self.caption_service = CaptionService(session)
    
    async def send_wish_for_pair(
        self,
        pair,
        user_a,
        user_b,
        pic_type: str,
        today: date,
        now_utc: datetime,
    ) -> bool:
        """Send wish for a pair if conditions are met.
        
        Args:
            pair: Pair object
            user_a: User A object
            user_b: User B object
            pic_type: Picture type ("morning" or "evening")
            today: Current date
            now_utc: Current UTC datetime
            
        Returns:
            True if wish was sent, False otherwise
        """
        def _skip(reason: str, **extra: object) -> bool:
            logger.debug(
                "Skipping wish send for pair",
                pair_id=getattr(pair, "id", None),
                pic_type=pic_type,
                reason=reason,
                **extra,
            )
            return False

        # Check if subscription is past due
        if pair.status == PairStatus.PAST_DUE.value:
            return _skip("pair_status_past_due")
        
        # Get daily state
        daily_state = await self.daily_state_repo.get_or_create(pair.id, today)
        
        # Check if already sent today
        if pic_type == "morning":
            if daily_state.morning_initiator is not None:
                return _skip("already_sent_today", initiator=daily_state.morning_initiator)
        else:  # evening
            if daily_state.evening_initiator is not None:
                return _skip("already_sent_today", initiator=daily_state.evening_initiator)
        
        # Check if at least one user is in their time window
        user_a_local_time = TimeWindowService.get_user_local_time(now_utc, user_a.utc_offset)
        user_b_local_time = TimeWindowService.get_user_local_time(now_utc, user_b.utc_offset)
        
        if pic_type == "morning":
            user_a_in_window = TimeWindowService.is_in_morning_window(user_a_local_time)
            user_b_in_window = TimeWindowService.is_in_morning_window(user_b_local_time)
        else:  # evening
            user_a_in_window = TimeWindowService.is_in_evening_window(user_a_local_time)
            user_b_in_window = TimeWindowService.is_in_evening_window(user_b_local_time)
        
        # If neither user is in their time window, skip
        if not user_a_in_window and not user_b_in_window:
            return _skip(
                "outside_time_window",
                user_a_local_time=str(user_a_local_time),
                user_b_local_time=str(user_b_local_time),
                user_a_utc_offset=getattr(user_a, "utc_offset", None),
                user_b_utc_offset=getattr(user_b, "utc_offset", None),
            )
        
        # Check wish request attempt limit (max 3 attempts per day with 1 hour intervals)
        wish_request_key_prefix = f"{settings.redis_key_prefix_wish_request}:{pair.id}:{pic_type}:{today.isoformat()}"
        first_sent_key = f"{wish_request_key_prefix}:first_sent"
        last_sent_key = f"{wish_request_key_prefix}:last_sent"
        count_key = f"{wish_request_key_prefix}:count"
        
        # Get current attempt count
        count_str = await self.lock_service.get_key(count_key)
        attempt_count = int(count_str) if count_str else 0
        
        # If already sent 3 attempts, don't send more
        if attempt_count >= 3:
            logger.debug(
                "Wish request limit reached for pair",
                pair_id=pair.id,
                pic_type=pic_type,
                attempt_count=attempt_count,
            )
            return _skip("attempt_limit_reached", attempt_count=attempt_count)
        
        # Check if we should send based on attempt count and time intervals
        if attempt_count == 0:
            # First attempt - send immediately
            should_send = True
        elif attempt_count == 1:
            # Second attempt - check if 1 hour passed since first
            first_sent_str = await self.lock_service.get_key(first_sent_key)
            if first_sent_str:
                try:
                    first_sent_time = datetime.fromisoformat(first_sent_str)
                    hours_passed = (now_utc - first_sent_time).total_seconds() / 3600
                    should_send = hours_passed >= 1.0
                except (ValueError, TypeError):
                    should_send = True  # If parsing fails, allow sending
            else:
                should_send = True  # If first_sent not found, allow sending
        else:  # attempt_count == 2
            # Third attempt - check if 1 hour passed since last
            last_sent_str = await self.lock_service.get_key(last_sent_key)
            if last_sent_str:
                try:
                    last_sent_time = datetime.fromisoformat(last_sent_str)
                    hours_passed = (now_utc - last_sent_time).total_seconds() / 3600
                    should_send = hours_passed >= 1.0
                except (ValueError, TypeError):
                    should_send = True  # If parsing fails, allow sending
            else:
                should_send = True  # If last_sent not found, allow sending
        
        if not should_send:
            logger.debug(
                "Wish request not sent - time interval not met",
                pair_id=pair.id,
                pic_type=pic_type,
                attempt_count=attempt_count,
            )
            return _skip("attempt_interval_not_met", attempt_count=attempt_count)
        
        # Build request message based on pair mode
        if pair.mode == "chat":
            if pic_type == "morning":
                request_text = get_message("WORKER_MORNING_REQUEST_CHAT")
            else:  # evening
                request_text = get_message("WORKER_EVENING_REQUEST_CHAT")
        else:  # silent
            if pic_type == "morning":
                request_text = get_message("WORKER_MORNING_REQUEST_SILENT")
            else:  # evening
                request_text = get_message("WORKER_EVENING_REQUEST_SILENT")
        
        # Send request to BOTH users (if at least one is in their time window)
        # Both users should receive the request, regardless of their individual time windows
        sent_to_a = False
        sent_to_b = False
        
        # Send to user_a
        # Check if user_a has multiple active pairs
        all_user_a_pairs = await self.pairs_repo.get_all_by_user_tg_id(user_a.tg_id)
        active_user_a_pairs = [
            p for p in all_user_a_pairs
            if p.status in ("trial", "active")
        ]
        has_multiple_pairs_a = len(active_user_a_pairs) > 1
        
        # Build callback data based on number of pairs
        if has_multiple_pairs_a:
            callback_prefix = "request_morning_all" if pic_type == "morning" else "request_evening_all"
            callback_data_a = f"{callback_prefix}_{user_a.id}"
        else:
            callback_prefix = "request_morning" if pic_type == "morning" else "request_evening"
            callback_data_a = f"{callback_prefix}_{pair.id}_{user_a.id}"
        
        button_text = get_message("WORKER_SEND_PICTURE_BUTTON")
        reply_markup_a = {
            "inline_keyboard": [
                [
                    {
                        "text": button_text,
                        "callback_data": callback_data_a,
                    },
                ],
            ],
        }
        
        try:
            await self.telegram_messenger.send_message(
                chat_id=user_a.tg_id,
                text=request_text,
                reply_markup=reply_markup_a,
            )
            sent_to_a = True
        except Exception as e:
            logger.error(
                "Error sending request to user_a",
                pair_id=pair.id,
                user_a_tg_id=user_a.tg_id,
                error=str(e),
                exc_info=True,
            )
        
        # Send to user_b
        # Check if user_b has multiple active pairs
        all_user_b_pairs = await self.pairs_repo.get_all_by_user_tg_id(user_b.tg_id)
        active_user_b_pairs = [
            p for p in all_user_b_pairs
            if p.status in ("trial", "active")
        ]
        has_multiple_pairs_b = len(active_user_b_pairs) > 1
        
        # Build callback data based on number of pairs
        if has_multiple_pairs_b:
            callback_prefix = "request_morning_all" if pic_type == "morning" else "request_evening_all"
            callback_data_b = f"{callback_prefix}_{user_b.id}"
        else:
            callback_prefix = "request_morning" if pic_type == "morning" else "request_evening"
            callback_data_b = f"{callback_prefix}_{pair.id}_{user_b.id}"
        
        reply_markup_b = {
            "inline_keyboard": [
                [
                    {
                        "text": button_text,
                        "callback_data": callback_data_b,
                    },
                ],
            ],
        }
        
        try:
            await self.telegram_messenger.send_message(
                chat_id=user_b.tg_id,
                text=request_text,
                reply_markup=reply_markup_b,
            )
            sent_to_b = True
        except Exception as e:
            logger.error(
                "Error sending request to user_b",
                pair_id=pair.id,
                user_b_tg_id=user_b.tg_id,
                error=str(e),
                exc_info=True,
            )
        
        if sent_to_a or sent_to_b:
            # Update wish request tracking in Redis
            new_count = attempt_count + 1
            now_iso = now_utc.isoformat()
            
            # Set first_sent time if this is the first attempt
            if attempt_count == 0:
                await self.lock_service.set_key_with_ttl(
                    first_sent_key,
                    now_iso,
                    86400,  # 24 hours TTL
                )
            
            # Always update last_sent time
            await self.lock_service.set_key_with_ttl(
                last_sent_key,
                now_iso,
                86400,  # 24 hours TTL
            )
            
            # Update attempt count
            await self.lock_service.set_key_with_ttl(
                count_key,
                str(new_count),
                86400,  # 24 hours TTL
            )
            
            logger.info(
                "Wish request sent to users",
                pair_id=pair.id,
                pic_type=pic_type,
                sent_to_user_a=sent_to_a,
                sent_to_user_b=sent_to_b,
                user_a_in_window=user_a_in_window,
                user_b_in_window=user_b_in_window,
                attempt_count=new_count,
            )
            return True
        
        return False

