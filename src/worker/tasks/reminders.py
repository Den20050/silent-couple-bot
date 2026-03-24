"""Reminder tasks for unanswered pictures."""

from datetime import date, datetime, timedelta
from typing import Any

from src.core.config import settings
from src.core.logger import get_logger
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.worker.di.context import WorkerContext
from src.worker.services.reminder_finder import ReminderFinder, WarningFinder
from src.worker.services.reminder_sender import ReminderSender, WarningSender
from src.worker.services.reminder_validator import ReminderValidator

logger = get_logger(__name__)


async def check_unanswered_pictures(
    ctx: dict[str, Any],
    worker_context: WorkerContext,
) -> None:
    """Check for unanswered pictures and send reminders.
    
    Args:
        ctx: Arq context
        worker_context: Worker context with dependencies
    """
    try:
        # Ensure bot is initialized
        await worker_context.ensure_bot_initialized()
        
        # Get LockService for tracking sent reminders
        lock_service = worker_context.lock_service
        
        async with worker_context.session_factory() as session:
            daily_state_repo = DailyStateRepository(session)
            pairs_repo = PairsRepository(session)
            users_repo = UsersRepository(session)
            
            logger.info("Starting check_unanswered_pictures task")
            
            # Process morning pictures
            await process_reminders_for_type(
                session=session,
                daily_state_repo=daily_state_repo,
                pairs_repo=pairs_repo,
                users_repo=users_repo,
                lock_service=lock_service,
                pic_type="morning",
                worker_context=worker_context,
            )
            
            # Process evening pictures
            await process_reminders_for_type(
                session=session,
                daily_state_repo=daily_state_repo,
                pairs_repo=pairs_repo,
                users_repo=users_repo,
                lock_service=lock_service,
                pic_type="evening",
                worker_context=worker_context,
            )
            
            await session.commit()
            logger.info("Completed check_unanswered_pictures task")
    finally:
        await worker_context.close_bot()
        await lock_service.close()


async def process_reminders_for_type(
    session,
    daily_state_repo: DailyStateRepository,
    pairs_repo: PairsRepository,
    users_repo: UsersRepository,
    lock_service,
    pic_type: str,
    worker_context: WorkerContext,
) -> None:
    """Process reminders for morning or evening pictures.
    
    Args:
        session: Database session
        daily_state_repo: DailyStateRepository instance
        pairs_repo: PairsRepository instance
        users_repo: UsersRepository instance
        lock_service: LockService instance
        pic_type: Picture type ("morning" or "evening")
        worker_context: Worker context with dependencies
    """
    # Initialize services
    reminder_finder = ReminderFinder(session, daily_state_repo, pairs_repo, users_repo)
    reminder_validator = ReminderValidator(daily_state_repo)
    reminder_sender = ReminderSender(worker_context)
    
    warning_finder = WarningFinder(session, daily_state_repo, pairs_repo, users_repo)
    warning_validator = ReminderValidator(daily_state_repo)
    warning_sender = WarningSender(worker_context)
    
    # Process reminders to recipient (from config)
    recipient_reminder_hours = settings.get_reminder_hours()
    
    logger.info(
        "Checking unanswered pictures for reminders",
        pic_type=pic_type,
        reminder_hours=recipient_reminder_hours,
    )

    for hours in recipient_reminder_hours:
        unanswered = await reminder_finder.find_unanswered_pictures(hours, pic_type)

        logger.info(
            "Found unanswered pictures",
            pic_type=pic_type,
            hours=hours,
            count=len(unanswered),
        )

        # Collect candidates per recipient and send one aggregated reminder per user.
        candidates_by_recipient: dict[int, list[ReminderCandidate]] = {}

        for state in unanswered:
            try:
                # Build candidate
                candidate = await reminder_finder.build_reminder_candidate(state, pic_type)
                if not candidate:
                    continue

                # Validate conditions
                if not await reminder_validator.should_send_reminder(candidate):
                    continue

                # Check Redis lock to prevent duplicate reminders
                reminder_key = (
                    f"{settings.redis_key_prefix_reminder_sent}:{candidate.pair.id}:{candidate.target_day}:{pic_type}:{hours}"
                )
                already_sent = await lock_service.check_key_exists(reminder_key)
                if already_sent:
                    continue

                # Mark reminder as sent for this pair/hour (so we don't retry)
                await lock_service.set_key_with_ttl(
                    reminder_key, "1", settings.reminder_ttl_hours * 3600
                )

                candidates_by_recipient.setdefault(candidate.recipient.tg_id, []).append(candidate)
            except Exception as e:
                logger.error(
                    "Error processing reminder",
                    pair_id=state.pair_id,
                    pic_type=pic_type,
                    hours=hours,
                    error=str(e),
                    exc_info=True,
                )
                continue

        # Send aggregated reminder per recipient.
        for recipient_tg_id, candidates in candidates_by_recipient.items():
            try:
                await reminder_sender.send_aggregated_reminder(candidates=candidates)
            except Exception as e:
                logger.error(
                    "Error sending aggregated reminder",
                    recipient_tg_id=recipient_tg_id,
                    pic_type=pic_type,
                    hours=hours,
                    error=str(e),
                    exc_info=True,
                )
                continue
    
    # Process warnings to initiator (10+ hours, every 6 hours)
    # Find all pictures sent more than 10 hours ago
    unanswered = await warning_finder.find_unanswered_pictures(10, pic_type)
    
    logger.info(
        "Checking unanswered pictures for warnings",
        pic_type=pic_type,
        count=len(unanswered),
    )
    
    now_utc = datetime.utcnow()
    warning_interval_hours = settings.warning_interval_hours
    
    for state in unanswered:
        try:
            # Build candidate
            candidate = await warning_finder.build_warning_candidate(state, pic_type)
            if not candidate:
                continue
            
            # Validate conditions
            if not await warning_validator.should_send_warning(candidate):
                continue
            
            # Check if warning cancelled
            cancel_key = (
                f"{settings.redis_key_prefix_warning_cancelled}:{candidate.pair.id}:{candidate.target_day}:{pic_type}"
            )
            cancelled = await lock_service.check_key_exists(cancel_key)
            if cancelled:
                continue
            
            # Check time since picture was sent
            sent_at = (
                state.morning_sent_at
                if pic_type == "morning"
                else state.evening_sent_at
            )
            if not sent_at:
                continue
            
            hours_since_sent = (now_utc - sent_at).total_seconds() / 3600
            
            # Only send if at least min hours have passed
            if hours_since_sent < settings.warning_min_hours:
                continue
            
            # Check last warning time
            last_warning_key = (
                f"{settings.redis_key_prefix_warning_last_time}:{candidate.pair.id}:{candidate.target_day}:{pic_type}"
            )
            last_warning_time = await lock_service.get_last_warning_time(last_warning_key)
            
            if last_warning_time:
                # Check if 6 hours have passed since last warning
                hours_since_last_warning = (now_utc.timestamp() - last_warning_time) / 3600
                if hours_since_last_warning < warning_interval_hours:
                    continue
            
            # Calculate hours to display (round down to nearest hour)
            hours_to_display = int(hours_since_sent)
            
            # Send warning
            await warning_sender.send_warning(
                candidate=candidate,
                hours=hours_to_display,
                warning_key=last_warning_key,  # Use same key for tracking
                lock_service=lock_service,
                pairs_repo=pairs_repo,
            )
            
            # Update last warning time
            await lock_service.set_last_warning_time(
                last_warning_key,
                now_utc.timestamp(),
                ttl_seconds=settings.warning_ttl_days * 24 * 3600,
            )
        except Exception as e:
            logger.error(
                "Error processing initiator warning",
                pair_id=state.pair_id,
                pic_type=pic_type,
                error=str(e),
                exc_info=True,
            )
            continue


# Internal functions moved to ReminderSender and WarningSender services


async def send_recipient_reminder(
    ctx: dict[str, Any],
    pair_id: int,
    recipient_tg_id: int,
    pic_type: str,
    hours: int,
    worker_context: WorkerContext,
) -> None:
    """Send reminder to recipient (called from scheduled job).
    
    Args:
        ctx: Arq context
        pair_id: Pair ID
        recipient_tg_id: Telegram ID of recipient
        pic_type: Picture type ("morning" or "evening")
        hours: Hours since picture was sent
        worker_context: Worker context with dependencies
    """
    try:
        # Ensure bot is initialized
        await worker_context.ensure_bot_initialized()
        
        async with worker_context.session_factory() as session:
            from src.core.constants import PairStatus
            from src.db.repositories.pairs import PairsRepository
            from src.db.repositories.users import UsersRepository
            from src.db.repositories.daily_state import DailyStateRepository
            
            pairs_repo = PairsRepository(session)
            users_repo = UsersRepository(session)
            daily_state_repo = DailyStateRepository(session)
            
            pair = await pairs_repo.get_by_id(pair_id)
            if not pair:
                return
            
            # Skip reminders for past_due pairs
            if pair.status == PairStatus.PAST_DUE.value:
                return
            
            # Get recipient
            recipient = await users_repo.get_by_tg_id(recipient_tg_id)
            if not recipient:
                return
            
            # Find the day when picture was sent
            # Check today and yesterday (for reminders that might be for previous day)
            today = date.today()
            target_day = None
            
            for check_day in [today, today - timedelta(days=1)]:
                daily_state = await daily_state_repo.get_by_pair_and_day(
                    pair_id,
                    check_day,
                )
                
                if not daily_state:
                    continue
                
                # Check if picture was sent and not answered
                if pic_type == "morning":
                    if daily_state.morning_initiator is None:
                        continue
                    if daily_state.morning_responded_at is not None:
                        continue
                    sent_at = daily_state.morning_sent_at
                else:  # evening
                    if daily_state.evening_initiator is None:
                        continue
                    if daily_state.evening_responded_at is not None:
                        continue
                    sent_at = daily_state.evening_sent_at
                
                if not sent_at:
                    continue
                
                # Check if enough hours have passed
                now_utc = datetime.utcnow()
                hours_passed = (now_utc - sent_at).total_seconds() / 3600
                
                if hours_passed >= hours - 0.5:  # Allow 30 min tolerance
                    target_day = check_day
                    break
            
            if not target_day:
                return
            
            # Build candidate using finder
            reminder_finder = ReminderFinder(session, daily_state_repo, pairs_repo, users_repo)
            state = await daily_state_repo.get_by_pair_and_day(pair_id, target_day)
            if not state:
                return
            
            candidate = await reminder_finder.build_reminder_candidate(state, pic_type)
            if not candidate:
                return

            reminder_validator = ReminderValidator(daily_state_repo)
            if not await reminder_validator.should_send_reminder(candidate):
                return
            
            reminder_key = (
                f"{settings.redis_key_prefix_reminder_sent}:{pair_id}:{target_day}:{pic_type}:{hours}"
            )
            
            # Use LockService for tracking
            lock_service = worker_context.lock_service

            already_sent = await lock_service.check_key_exists(reminder_key)
            if already_sent:
                return
            
            # Send reminder using sender service
            reminder_sender = ReminderSender(worker_context)
            await reminder_sender.send_reminder(
                candidate=candidate,
                reminder_key=reminder_key,
                lock_service=lock_service,
            )
    finally:
        await worker_context.close_bot()


async def send_initiator_warning(
    ctx: dict[str, Any],
    pair_id: int,
    initiator_tg_id: int,
    recipient_user_id: int,
    pic_type: str,
    hours: int,
    worker_context: WorkerContext,
) -> None:
    """Send warning to initiator (called from scheduled job).
    
    Args:
        ctx: Arq context
        pair_id: Pair ID
        initiator_tg_id: Telegram ID of initiator
        recipient_user_id: User ID of recipient
        pic_type: Picture type ("morning" or "evening")
        hours: Hours since picture was sent
        worker_context: Worker context with dependencies
    """
    try:
        # Ensure bot is initialized
        await worker_context.ensure_bot_initialized()
        
        async with worker_context.session_factory() as session:
            from src.core.constants import PairStatus
            from src.db.repositories.pairs import PairsRepository
            from src.db.repositories.users import UsersRepository
            from src.db.repositories.daily_state import DailyStateRepository
            
            pairs_repo = PairsRepository(session)
            users_repo = UsersRepository(session)
            daily_state_repo = DailyStateRepository(session)
            
            pair = await pairs_repo.get_by_id(pair_id)
            if not pair:
                return
            
            # Skip warnings for past_due pairs
            if pair.status == PairStatus.PAST_DUE.value:
                return
            
            # Get users
            user_a = await users_repo.get_by_id(pair.uid_a)
            user_b = await users_repo.get_by_id(pair.uid_b)
            if not user_a or not user_b:
                return
            
            initiator = await users_repo.get_by_tg_id(initiator_tg_id)
            recipient = (
                user_a if recipient_user_id == user_a.id else user_b
            )
            
            if not initiator or not recipient:
                return
            
            # Find the day when picture was sent
            # Check today and yesterday (for warnings that might be for previous day)
            today = date.today()
            target_day = None
            
            for check_day in [today, today - timedelta(days=1)]:
                daily_state = await daily_state_repo.get_by_pair_and_day(
                    pair_id,
                    check_day,
                )
                
                if not daily_state:
                    continue
                
                # Check if picture was sent and not answered
                if pic_type == "morning":
                    if daily_state.morning_initiator is None:
                        continue
                    if daily_state.morning_responded_at is not None:
                        continue
                    sent_at = daily_state.morning_sent_at
                else:  # evening
                    if daily_state.evening_initiator is None:
                        continue
                    if daily_state.evening_responded_at is not None:
                        continue
                    sent_at = daily_state.evening_sent_at
                
                if not sent_at:
                    continue
                
                # Check if enough hours have passed
                now_utc = datetime.utcnow()
                hours_passed = (now_utc - sent_at).total_seconds() / 3600
                
                if hours_passed >= hours - 0.5:  # Allow 30 min tolerance
                    # Check if recipient has already responded to the other picture type
                    if pic_type == "morning":
                        if daily_state.evening_responded_at is not None:
                            continue
                    else:  # evening
                        if daily_state.morning_responded_at is not None:
                            continue
                    
                    target_day = check_day
                    break
            
            if not target_day:
                return
            
            # Build candidate using finder
            warning_finder = WarningFinder(session, daily_state_repo, pairs_repo, users_repo)
            state = await daily_state_repo.get_by_pair_and_day(pair_id, target_day)
            if not state:
                return
            
            candidate = await warning_finder.build_warning_candidate(state, pic_type)
            if not candidate:
                return

            warning_validator = ReminderValidator(daily_state_repo)
            if not await warning_validator.should_send_warning(candidate):
                return
            
            # Use LockService for tracking
            lock_service = worker_context.lock_service
            
            # Check if warning cancelled
            cancel_key = (
                f"{settings.redis_key_prefix_warning_cancelled}:{pair_id}:{target_day}:{pic_type}"
            )
            cancelled = await lock_service.check_key_exists(cancel_key)
            if cancelled:
                return
            
            # Use last warning time key for tracking
            warning_key = (
                f"{settings.redis_key_prefix_warning_last_time}:{pair_id}:{target_day}:{pic_type}"
            )

            # Throttle warnings (idempotency across retries / multiple schedulers)
            last_warning_time = await lock_service.get_last_warning_time(warning_key)
            if last_warning_time is not None:
                now_ts = datetime.utcnow().timestamp()
                hours_since_last_warning = (now_ts - last_warning_time) / 3600
                if hours_since_last_warning < settings.warning_interval_hours:
                    return
            
            # Send warning using sender service
            warning_sender = WarningSender(worker_context)
            await warning_sender.send_warning(
                candidate=candidate,
                hours=hours,
                warning_key=warning_key,
                lock_service=lock_service,
                pairs_repo=pairs_repo,
            )

            await lock_service.set_last_warning_time(
                warning_key,
                datetime.utcnow().timestamp(),
            )
    finally:
        await worker_context.close_bot()


