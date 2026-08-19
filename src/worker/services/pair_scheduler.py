"""Pair scheduling service for sending wishes and reminders."""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus
from src.core.config import settings
from src.core.logger import get_logger
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.image import ImageService
from src.services.messaging.caption_service import CaptionService
from src.core.protocols.messenger import MessengerProtocol
from src.services.pair_time_window import is_user_in_time_window
from src.worker.services.lock_service import LockService

from src.services.messaging.ui.wish_request_ui import WishRequestUIService
from src.services.messaging.active_action_message import activate_message, ActionKind

logger = get_logger(__name__)

_WISH_REQUEST_PROMPT_MESSAGE_TTL_SECONDS = 48 * 3600
_SEND_BATCH_SIZE = 25
_SEND_BATCH_INTERVAL_S = 1.0


def _wish_request_prompt_message_id_key(tg_id: int, pic_type: str, day: date) -> str:
    return f"wish_request_prompt_message_id:{tg_id}:{pic_type}:{day.isoformat()}"


def _keyboard_has_send_actions(reply_markup: dict, pic_type: str) -> bool:
    prefix = f"request_{pic_type}_"
    for row in reply_markup.get("inline_keyboard", []):
        for button in row:
            callback_data = button.get("callback_data", "")
            if callback_data.startswith(prefix):
                return True
    return False


def _user_attempt_key_prefix(user_id: int, pic_type: str, day: date) -> str:
    return (
        f"{settings.redis_key_prefix_wish_request}:user:{user_id}:"
        f"{pic_type}:{day.isoformat()}"
    )


@dataclass(frozen=True)
class WishRequestAttemptContext:
    """Redis attempt-tracking context for a user/day/pic_type."""

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
        self.session = session
        self.telegram_messenger = telegram_messenger
        self.lock_service = lock_service
        self.pairs_repo = PairsRepository(session)
        self.daily_state_repo = DailyStateRepository(session)
        self.users_repo = UsersRepository(session)
        self.image_service = ImageService(session)
        self.caption_service = CaptionService(session)

    async def _mark_attempt_sent(
        self, ctx: WishRequestAttemptContext, now_utc: datetime
    ) -> None:
        new_count = ctx.attempt_count + 1
        now_iso = now_utc.isoformat()

        if ctx.attempt_count == 0:
            await self.lock_service.set_key_with_ttl(
                ctx.first_sent_key, now_iso, 86400
            )

        await self.lock_service.set_key_with_ttl(ctx.last_sent_key, now_iso, 86400)
        await self.lock_service.set_key_with_ttl(ctx.count_key, str(new_count), 86400)

    async def check_pair_needs_wish_prompt(
        self,
        pair,
        pic_type: str,
        today: date,
    ) -> tuple[bool, str]:
        """Return whether a pair still needs a wish today (ignores time windows)."""
        if pair.status == PairStatus.PAST_DUE.value:
            return False, "pair_status_past_due"

        daily_state = await self.daily_state_repo.get_or_create(pair.id, today)

        if pic_type == "morning":
            if daily_state.morning_initiator is not None:
                return False, "already_sent_today"
        elif pic_type == "evening":
            if daily_state.evening_initiator is not None:
                return False, "already_sent_today"
        else:
            return False, "invalid_pic_type"

        return True, "pair_needs_prompt"

    async def should_prompt_user(
        self,
        user,
        pic_type: str,
        today: date,
        now_utc: datetime,
    ) -> tuple[bool, str, WishRequestAttemptContext | None]:
        """Check if this user should receive a wish-request prompt now."""
        if pic_type not in ("morning", "evening"):
            return False, "invalid_pic_type", None

        if not is_user_in_time_window(user, pic_type, now_utc):  # type: ignore[arg-type]
            return False, "outside_time_window", None

        prefix = _user_attempt_key_prefix(user.id, pic_type, today)
        first_sent_key = f"{prefix}:first_sent"
        last_sent_key = f"{prefix}:last_sent"
        count_key = f"{prefix}:count"

        count_str = await self.lock_service.get_key(count_key)
        attempt_count = int(count_str) if count_str else 0

        if attempt_count >= 3:
            return False, "attempt_limit_reached", None

        if attempt_count == 0:
            should_send = True
        elif attempt_count == 1:
            first_sent_str = await self.lock_service.get_key(first_sent_key)
            if first_sent_str:
                try:
                    first_sent_time = datetime.fromisoformat(first_sent_str)
                    hours_passed = (now_utc - first_sent_time).total_seconds() / 3600
                    should_send = hours_passed >= 1.0
                except (ValueError, TypeError):
                    should_send = True
            else:
                should_send = True
        else:
            last_sent_str = await self.lock_service.get_key(last_sent_key)
            if last_sent_str:
                try:
                    last_sent_time = datetime.fromisoformat(last_sent_str)
                    hours_passed = (now_utc - last_sent_time).total_seconds() / 3600
                    should_send = hours_passed >= 1.0
                except (ValueError, TypeError):
                    should_send = True
            else:
                should_send = True

        if not should_send:
            return False, "attempt_interval_not_met", None

        ctx = WishRequestAttemptContext(
            first_sent_key=first_sent_key,
            last_sent_key=last_sent_key,
            count_key=count_key,
            attempt_count=attempt_count,
        )
        return True, "eligible", ctx

    async def _send_prompt_to_user(
        self,
        tg_id: int,
        ui_builder: WishRequestUIService,
        pic_type: str,
        today: date,
        now_utc: datetime,
    ) -> bool:
        try:
            ui = await ui_builder.build_for_user(
                user_tg_id=tg_id,
                pic_type=pic_type,
                day=today,
                now_utc=now_utc,
            )
            if not _keyboard_has_send_actions(ui.reply_markup, pic_type):
                logger.debug(
                    "Skipping wish prompt: no send actions for user",
                    tg_id=tg_id,
                    pic_type=pic_type,
                )
                return False

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
                        if "message is not modified" not in str(e).lower():
                            raise
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
                    return True
                except Exception:
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
            return True

        except Exception as e:
            logger.error(
                "Failed to send/update aggregated wish request prompt",
                tg_id=tg_id,
                pic_type=pic_type,
                error=str(e),
                exc_info=True,
            )
            return False

    async def send_aggregated_wish_requests(
        self,
        user_to_pair_ids: dict[int, set[int]],
        pic_type: str,
        today: date,
        now_utc: datetime,
        attempt_ctx_by_tg_id: dict[int, WishRequestAttemptContext],
    ) -> tuple[int, set[int]]:
        """Send/update aggregated wish request prompts for specified users."""
        ui_builder = WishRequestUIService(self.session)
        updated = 0
        succeeded: set[int] = set()

        items = list(user_to_pair_ids.items())

        for batch_start in range(0, len(items), _SEND_BATCH_SIZE):
            batch = items[batch_start : batch_start + _SEND_BATCH_SIZE]

            results: list[bool] = await asyncio.gather(  # type: ignore[assignment]
                *[
                    self._send_prompt_to_user(
                        tg_id, ui_builder, pic_type, today, now_utc
                    )
                    for tg_id, _pair_ids in batch
                ]
            )

            for (tg_id, _pair_ids), success in zip(batch, results):
                if success:
                    updated += 1
                    succeeded.add(tg_id)

            if batch_start + _SEND_BATCH_SIZE < len(items):
                await asyncio.sleep(_SEND_BATCH_INTERVAL_S)

        for tg_id in succeeded:
            ctx = attempt_ctx_by_tg_id.get(tg_id)
            if ctx is None:
                continue
            try:
                await self._mark_attempt_sent(ctx, now_utc=now_utc)
            except Exception as e:
                logger.warning(
                    "Failed to mark wish request attempt as sent",
                    tg_id=tg_id,
                    pic_type=pic_type,
                    error=str(e),
                )

        return updated, succeeded
