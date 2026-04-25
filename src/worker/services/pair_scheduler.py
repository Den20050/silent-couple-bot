"""Pair scheduling service for sending wishes and reminders."""

from datetime import date, datetime, timedelta
from datetime import time as time_type
import hashlib
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
from dataclasses import dataclass

from src.services.messaging.ui.wish_request_ui import WishRequestUIService
from src.services.messaging.active_action_message import activate_message, ActionKind

logger = get_logger(__name__)

_WISH_REQUEST_PROMPT_MESSAGE_TTL_SECONDS = 48 * 3600


def _wish_request_prompt_message_id_key(tg_id: int, pic_type: str, day: date) -> str:
    """Redis key for storing single aggregated request prompt message_id."""
    return f"wish_request_prompt_message_id:{tg_id}:{pic_type}:{day.isoformat()}"


def _pair_minute_slot(pair_id: int, pic_type: str, day: date) -> int:
    """Return deterministic 0..59 minute slot for pair/day/type.

    Spreads sends uniformly inside a 1-hour user window to avoid peak load.
    """
    seed = f"{pair_id}:{pic_type}:{day.isoformat()}".encode("utf-8")
    digest = hashlib.md5(seed).hexdigest()
    return int(digest[:8], 16) % 60


@dataclass(frozen=True)
class WishRequestAttemptContext:
    """Redis attempt-tracking context for a pair/day/pic_type."""

    first_sent_key: str
    last_sent_key: str
    count_key: str
    attempt_count: int


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
    
    # NOTE: public-ish DTO so worker tasks can track attempt state per pair


    async def _mark_attempt_sent(self, ctx: WishRequestAttemptContext, now_utc: datetime) -> None:
        """Update Redis attempt tracking for a pair/pic_type/day after we notified at least one user."""
        new_count = ctx.attempt_count + 1
        now_iso = now_utc.isoformat()

        if ctx.attempt_count == 0:
            await self.lock_service.set_key_with_ttl(ctx.first_sent_key, now_iso, 86400)

        await self.lock_service.set_key_with_ttl(ctx.last_sent_key, now_iso, 86400)
        await self.lock_service.set_key_with_ttl(ctx.count_key, str(new_count), 86400)

    async def send_wish_for_pair(
        self,
        pair,
        user_a,
        user_b,
        pic_type: str,
        today: date,
        now_utc: datetime,
    ) -> tuple[bool, str, WishRequestAttemptContext | None]:
        """Plan wish request for a pair (does NOT send messages directly).
        
        Args:
            pair: Pair object
            user_a: User A object
            user_b: User B object
            pic_type: Picture type ("morning" or "evening")
            today: Current date
            now_utc: Current UTC datetime
            
        Returns:
            Tuple of (should_notify, reason). If should_notify is False, reason describes skip cause.
        """
        def _skip(reason: str, **extra: object) -> tuple[bool, str]:
            logger.debug(
                "Skipping wish send for pair",
                pair_id=getattr(pair, "id", None),
                pic_type=pic_type,
                reason=reason,
                **extra,
            )
            return False, reason

        # Check if subscription is past due
        if pair.status == PairStatus.PAST_DUE.value:
            ok, reason = _skip("pair_status_past_due")
            return ok, reason, None
        
        # Get daily state
        daily_state = await self.daily_state_repo.get_or_create(pair.id, today)
        
        # Check if already sent today
        if pic_type == "morning":
            if daily_state.morning_initiator is not None:
                ok, reason = _skip(
                    "already_sent_today", initiator=daily_state.morning_initiator
                )
                return ok, reason, None
        else:  # evening
            if daily_state.evening_initiator is not None:
                ok, reason = _skip(
                    "already_sent_today", initiator=daily_state.evening_initiator
                )
                return ok, reason, None
        
        # Check if at least one user is in their time window (per-user preferences)
        user_a_local_time = TimeWindowService.get_user_local_time(now_utc, user_a.utc_offset)
        user_b_local_time = TimeWindowService.get_user_local_time(now_utc, user_b.utc_offset)
        
        def _window_for_user(user_obj, which: str) -> tuple[time_type, time_type]:
            # If pair has a window owner, windows become shared for the pair.
            # Otherwise, keep backward-compatible behavior: per-user windows.
            shared_owner_id = getattr(pair, "notification_window_owner_id", None)
            if shared_owner_id is not None:
                if which == "morning":
                    start_hour = getattr(pair, "morning_window_start_hour", None)
                else:
                    start_hour = getattr(pair, "evening_window_start_hour", None)
            else:
                if which == "morning":
                    start_hour = getattr(user_obj, "morning_window_start_hour", None)
                else:
                    start_hour = getattr(user_obj, "evening_window_start_hour", None)

            # Fallback to global config windows if field is missing (e.g., before migration)
            if start_hour is None:
                if which == "morning":
                    return settings.morning_start_time, settings.morning_end_time
                return settings.evening_start_time, settings.evening_end_time

            start = time_type(int(start_hour), 0)
            end = time_type((int(start_hour) + 1) % 24, 0)
            return start, end

        if pic_type == "morning":
            a_start, a_end = _window_for_user(user_a, "morning")
            b_start, b_end = _window_for_user(user_b, "morning")
        else:
            a_start, a_end = _window_for_user(user_a, "evening")
            b_start, b_end = _window_for_user(user_b, "evening")

        user_a_in_window = TimeWindowService.is_in_time_window(user_a_local_time, a_start, a_end)
        user_b_in_window = TimeWindowService.is_in_time_window(user_b_local_time, b_start, b_end)
        
        # If neither user is in their time window, skip
        if not user_a_in_window and not user_b_in_window:
            ok, reason = _skip(
                "outside_time_window",
                user_a_local_time=str(user_a_local_time),
                user_b_local_time=str(user_b_local_time),
                user_a_utc_offset=getattr(user_a, "utc_offset", None),
                user_b_utc_offset=getattr(user_b, "utc_offset", None),
            )
            return ok, reason, None

        # Deterministic minute slot spreading inside the selected hour window.
        # This prevents load spikes when many users pick the same hour.
        slot_minute = _pair_minute_slot(pair.id, pic_type, today)
        if now_utc.minute != slot_minute:
            ok, reason = _skip(
                "minute_slot_mismatch",
                current_minute=now_utc.minute,
                slot_minute=slot_minute,
            )
            return ok, reason, None
        
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
            ok, reason = _skip("attempt_limit_reached", attempt_count=attempt_count)
            return ok, reason, None
        
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
            ok, reason = _skip("attempt_interval_not_met", attempt_count=attempt_count)
            return ok, reason, None
        
        attempt_ctx = WishRequestAttemptContext(
            first_sent_key=first_sent_key,
            last_sent_key=last_sent_key,
            count_key=count_key,
            attempt_count=attempt_count,
        )

        # If we reached here, the pair is eligible to be included in the aggregated prompt.
        return True, "eligible", attempt_ctx

    async def send_aggregated_wish_requests(
        self,
        user_to_pair_ids: dict[int, set[int]],
        pic_type: str,
        today: date,
        now_utc: datetime,
        attempt_ctx_by_pair_id: dict[int, WishRequestAttemptContext],
    ) -> tuple[int, set[int], set[int]]:
        """Send/update aggregated wish request prompts for specified users.

        Returns:
            (users_updated_count, successfully_notified_user_tg_ids, pairs_marked_as_attempt_sent)
        """
        ui_builder = WishRequestUIService(self.session)
        updated = 0
        succeeded: set[int] = set()
        delivered_pair_ids: set[int] = set()

        for tg_id, pair_ids in user_to_pair_ids.items():
            try:
                ui = await ui_builder.build_for_user(
                    user_tg_id=tg_id,
                    pic_type=pic_type,
                    day=today,
                )
                key = _wish_request_prompt_message_id_key(tg_id, pic_type, today)
                message_id_raw = await self.lock_service.get_key(key)
                if message_id_raw:
                    try:
                        message_id = int(message_id_raw)
                        try:
                            await self.telegram_messenger.edit_message(
                                chat_id=tg_id,
                                message_id=message_id,
                                text=ui.text,
                                reply_markup=ui.reply_markup,
                            )
                        except Exception as e:
                            # Telegram may reject a no-op edit with "message is not modified".
                            # Treat it as success to avoid spamming users with new messages.
                            if "message is not modified" not in str(e).lower():
                                raise
                        # Keep only this message interactive for the user (best-effort).
                        # IMPORTANT: activation must never be fatal; otherwise we can spam users
                        # with repeated prompts on every cron tick.
                        try:
                            await activate_message(
                                redis=await self.lock_service.get_redis_client(),
                                messenger=self.telegram_messenger,
                                tg_id=tg_id,
                                message_id=message_id,
                                kind=ActionKind.PROMPT,
                            )
                        except Exception as e:
                            logger.warning(
                                "Failed to activate prompt message",
                                tg_id=tg_id,
                                pic_type=pic_type,
                                message_id=message_id,
                                error=str(e),
                            )
                        updated += 1
                        succeeded.add(tg_id)
                        delivered_pair_ids.update(pair_ids)
                        continue
                    except Exception:
                        # If edit fails (message deleted, etc.), fall back to sending a new prompt.
                        pass

                msg = await self.telegram_messenger.send_message(
                    chat_id=tg_id,
                    text=ui.text,
                    reply_markup=ui.reply_markup,
                )
                await self.lock_service.set_key_with_ttl(
                    key,
                    str(msg.message_id),
                    _WISH_REQUEST_PROMPT_MESSAGE_TTL_SECONDS,
                )
                # Best-effort: don't let activation errors break idempotency.
                try:
                    await activate_message(
                        redis=await self.lock_service.get_redis_client(),
                        messenger=self.telegram_messenger,
                        tg_id=tg_id,
                        message_id=msg.message_id,
                        kind=ActionKind.PROMPT,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to activate prompt message",
                        tg_id=tg_id,
                        pic_type=pic_type,
                        message_id=msg.message_id,
                        error=str(e),
                    )
                updated += 1
                succeeded.add(tg_id)
                delivered_pair_ids.update(pair_ids)
            except Exception as e:
                logger.error(
                    "Failed to send/update aggregated wish request prompt",
                    tg_id=tg_id,
                    pic_type=pic_type,
                    error=str(e),
                    exc_info=True,
                )

        # Mark attempt tracking only for pairs for which at least one user prompt succeeded.
        pairs_marked: set[int] = set()
        for pair_id in delivered_pair_ids:
            ctx = attempt_ctx_by_pair_id.get(pair_id)
            if ctx is None:
                continue
            try:
                await self._mark_attempt_sent(ctx, now_utc=now_utc)
                pairs_marked.add(pair_id)
            except Exception as e:
                logger.warning(
                    "Failed to mark wish request attempt as sent",
                    pair_id=pair_id,
                    pic_type=pic_type,
                    error=str(e),
                )

        return updated, succeeded, pairs_marked

