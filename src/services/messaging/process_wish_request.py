"""Shared wish-request processing for callbacks and Mini App."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.constants import PairStatus
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.services.messaging.active_action_message import ActionKind, is_message_active
from src.services.messaging.ui.wish_request_ui import WishRequestUIService
from src.services.messaging.wish_request_prompt_refresher import (
    prompt_message_id_key,
    refresh_aggregated_wish_prompt,
)
from src.services.pair_time_window import can_user_send_wish
from src.services.telegram.messenger import TelegramMessenger
from src.bot.handlers.callbacks.validators import validate_pair_and_user
from src.bot.handlers.callbacks.use_cases.send_wish import send_wish_to_partner
from src.bot.handlers.callbacks.use_cases.schedule_reminders import schedule_reminder_tasks
from src.bot.handlers.start.services.pair_service import format_partner_text

logger = get_logger(__name__)


@dataclass(frozen=True)
class WishRequestProcessResult:
    ok: bool
    error_message: str | None = None


async def _resolve_prompt_message_id(
    redis,
    tg_id: int,
    pic_type: str,
    day: date,
    prompt_message_id: int | None,
) -> int | None:
    if prompt_message_id is not None:
        return prompt_message_id
    if redis is None:
        return None
    try:
        raw = await redis.get(prompt_message_id_key(tg_id, pic_type, day))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return int(raw)
    except Exception:
        return None


async def process_wish_request(
    *,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
    settings: Settings,
    redis,
    tg_id: int,
    pair_id: int,
    user_id: int,
    pic_type: str,
    day: date,
    prompt_message_id: int | None = None,
) -> WishRequestProcessResult:
    """Send a wish for one pair and refresh aggregated prompts."""
    resolved_prompt_id = await _resolve_prompt_message_id(
        redis, tg_id, pic_type, day, prompt_message_id
    )
    if resolved_prompt_id is not None:
        ok = await is_message_active(
            redis=redis,
            tg_id=tg_id,
            message_id=resolved_prompt_id,
            kind=ActionKind.PROMPT,
        )
        if not ok:
            try:
                await telegram_messenger.remove_reply_markup(
                    chat_id=tg_id,
                    message_id=resolved_prompt_id,
                )
            except Exception:
                pass
            return WishRequestProcessResult(ok=False)

    pairs_repo = PairsRepository(session)
    pair = await pairs_repo.get_by_id(pair_id)
    if not pair:
        return WishRequestProcessResult(
            ok=False,
            error_message=get_message("CALLBACK_ERROR_GENERIC"),
        )

    if pair.status == PairStatus.PAST_DUE.value:
        await telegram_messenger.send_message(
            chat_id=tg_id,
            text=get_message("WORKER_PAST_DUE_DUNNING"),
        )
        return WishRequestProcessResult(ok=False)

    validation_result = await validate_pair_and_user(session, pair_id, user_id, tg_id)
    if not validation_result:
        return WishRequestProcessResult(
            ok=False,
            error_message=get_message("CALLBACK_ERROR_GENERIC"),
        )

    pair, user_a, user_b, user = validation_result

    if not can_user_send_wish(user, pic_type, datetime.utcnow()):  # type: ignore[arg-type]
        await telegram_messenger.send_message(
            chat_id=tg_id,
            text=get_message("CALLBACK_SEND_PERIOD_CLOSED"),
        )
        return WishRequestProcessResult(ok=False)

    daily_state_repo = DailyStateRepository(session)
    ui_builder = WishRequestUIService(session)

    success, _partner_nickname, delivered_immediately = await send_wish_to_partner(
        session=session,
        pair=pair,
        user_id=user_id,
        tg_id=tg_id,
        pic_type=pic_type,
        today=day,
        telegram_messenger=telegram_messenger,
        redis=redis,
    )

    if not success:
        daily_state = await daily_state_repo.get_by_pair_and_day(pair_id, day)
        initiator_field = (
            daily_state.morning_initiator
            if pic_type == "morning"
            else daily_state.evening_initiator
        ) if daily_state else None

        if initiator_field is not None and resolved_prompt_id is not None:
            try:
                ui = await ui_builder.build_for_user(
                    user_tg_id=tg_id, pic_type=pic_type, day=day
                )
                await telegram_messenger.edit_message(
                    chat_id=tg_id,
                    message_id=resolved_prompt_id,
                    text=ui.text,
                    reply_markup=ui.reply_markup,
                )
            except Exception:
                pass
            await telegram_messenger.send_message(
                chat_id=tg_id,
                text=get_message("CALLBACK_PARTNER_ALREADY_SENT"),
            )
        else:
            await telegram_messenger.send_message(
                chat_id=tg_id,
                text=get_message("CALLBACK_NO_IMAGES_AVAILABLE"),
            )
        return WishRequestProcessResult(ok=False)

    if resolved_prompt_id is not None:
        ui = await ui_builder.build_for_user(
            user_tg_id=tg_id, pic_type=pic_type, day=day
        )
        await telegram_messenger.edit_message(
            chat_id=tg_id,
            message_id=resolved_prompt_id,
            text=ui.text,
            reply_markup=ui.reply_markup,
        )

    partner_tg_id = user_b.tg_id if user_a.tg_id == tg_id else user_a.tg_id
    await refresh_aggregated_wish_prompt(
        session=session,
        telegram_messenger=telegram_messenger,
        tg_id=partner_tg_id,
        pic_type=pic_type,
        day=day,
    )

    partner_user = user_b if user_a.id == user_id else user_a
    partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user_id)
    partner_text = format_partner_text(
        partner_user.username if partner_user else None,
        partner_nickname,
    )
    await telegram_messenger.send_message(
        chat_id=tg_id,
        text=get_message(
            "CALLBACK_WISH_DELIVERED"
            if delivered_immediately
            else "CALLBACK_WISH_DELIVERY_DEFERRED",
            partner_text=partner_text,
        ),
    )

    if delivered_immediately:
        recipient_user = user_b if user_a.id == user_id else user_a
        await schedule_reminder_tasks(
            pair_id=pair_id,
            initiator_tg_id=tg_id,
            recipient_tg_id=partner_tg_id,
            recipient_user_id=recipient_user.id,
            pic_type=pic_type,
            settings=settings,
        )

    logger.info(
        "Wish request processed",
        tg_id=tg_id,
        pair_id=pair_id,
        pic_type=pic_type,
        day=str(day),
    )
    return WishRequestProcessResult(ok=True)
