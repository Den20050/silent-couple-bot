"""Morning request handlers."""

from datetime import date

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus
from src.core.messages import get_message
from src.core.logger import get_logger
from src.core.config import Settings
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.services.telegram.messenger import TelegramMessenger
from src.core.di.container import Container
from src.bot.handlers.callbacks.validators import (
    parse_callback_data,
    validate_pair_and_user,
)
from src.bot.handlers.callbacks.use_cases.send_wish import (
    send_wish_to_partner,
)
from src.bot.handlers.callbacks.use_cases.schedule_reminders import (
    schedule_reminder_tasks,
)
from src.services.messaging.ui.wish_request_ui import WishRequestUIService
from src.services.messaging.wish_request_prompt_refresher import refresh_aggregated_wish_prompt
from src.services.messaging.active_action_message import is_message_active, ActionKind
from src.bot.handlers.start.services.pair_service import format_partner_text

logger = get_logger(__name__)

router = Router(name="morning_requests")


async def _safe_callback_answer(
    callback: CallbackQuery,
    text: str | None = None,
    show_alert: bool = False,
) -> None:
    """Answer callback without failing handler on stale/expired query IDs."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as exc:
        message = str(exc).lower()
        if "query is too old" in message or "query id is invalid" in message:
            logger.warning("Ignored expired callback answer", error=str(exc))
            return
        logger.warning("Telegram bad request while answering callback", error=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Unexpected callback.answer failure", error=str(exc))


@router.callback_query(F.data.startswith("request_morning_all_"))
async def handle_request_morning_all_legacy(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Legacy handler: 'send to all' is deprecated; convert prompt to per-partner UI."""
    parsed = parse_callback_data(
        callback.data, expected_parts=4, prefix="request_morning_all_"
    )
    if not parsed:
        await _safe_callback_answer(callback, get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    (user_id,) = parsed
    tg_id = callback.from_user.id

    # Ensure the callback belongs to the same user (basic safety)
    from src.db.repositories.users import UsersRepository

    users_repo = UsersRepository(session)
    user = await users_repo.get_by_id(user_id)
    if not user or user.tg_id != tg_id:
        await _safe_callback_answer(callback, get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    today = date.today()
    ui_builder = WishRequestUIService(session)
    ui = await ui_builder.build_for_user(user_tg_id=tg_id, pic_type="morning", day=today)

    await telegram_messenger.edit_message(
        chat_id=tg_id,
        message_id=callback.message.message_id,
        text=ui.text,
        reply_markup=ui.reply_markup,
    )
    await _safe_callback_answer(callback, "ℹ️ Выберите партнёра")


@router.callback_query(F.data.startswith("request_morning_"))
async def handle_request_morning(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
    settings: Settings,
    container: Container,
) -> None:
    """Handle morning request button."""
    tg_id = callback.from_user.id

    # Answer the callback FIRST so the button spinner dismisses immediately
    # (~200-500ms for the proxy round-trip). All heavy DB/API work comes after.
    await _safe_callback_answer(callback)

    if callback.message:
        ok = await is_message_active(
            redis=container.redis,
            tg_id=tg_id,
            message_id=callback.message.message_id,
            kind=ActionKind.PROMPT,
        )
        if not ok:
            await telegram_messenger.remove_reply_markup(
                chat_id=tg_id,
                message_id=callback.message.message_id,
            )
            return

    # Parse callback data: request_morning_{pair_id}_{user_id}
    parsed = parse_callback_data(callback.data, expected_parts=4, prefix="request_morning_")
    if not parsed:
        return

    pair_id, user_id = parsed

    logger.info(
        "Processing request_morning callback",
        pair_id=pair_id,
        user_id=user_id,
        tg_id=tg_id,
        callback_data=callback.data,
    )

    # Validate pair and user
    validation_result = await validate_pair_and_user(
        session, pair_id, user_id, tg_id
    )
    if not validation_result:
        return

    pair, user_a, user_b, user = validation_result

    # Check if subscription is past due — send as a regular message (callback already answered)
    if pair.status == PairStatus.PAST_DUE.value:
        await telegram_messenger.send_message(
            chat_id=tg_id,
            text=get_message("WORKER_PAST_DUE_DUNNING"),
        )
        return

    today = date.today()
    daily_state_repo = DailyStateRepository(session)
    ui_builder = WishRequestUIService(session)

    # Send wish to partner
    success, partner_nickname = await send_wish_to_partner(
        session=session,
        pair=pair,
        user_id=user_id,
        tg_id=tg_id,
        pic_type="morning",
        today=today,
        telegram_messenger=telegram_messenger,
        redis=container.redis,
    )

    if not success:
        # Check if partner already sent
        daily_state = await daily_state_repo.get_by_pair_and_day(pair_id, today)
        if daily_state and daily_state.morning_initiator is not None:
            # Refresh UI (best effort) so the user sees "sent" status.
            try:
                ui = await ui_builder.build_for_user(
                    user_tg_id=tg_id, pic_type="morning", day=today
                )
                await telegram_messenger.edit_message(
                    chat_id=tg_id,
                    message_id=callback.message.message_id,
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
        return

    # Success: refresh the aggregated prompt
    ui = await ui_builder.build_for_user(user_tg_id=tg_id, pic_type="morning", day=today)
    await telegram_messenger.edit_message(
        chat_id=tg_id,
        message_id=callback.message.message_id,
        text=ui.text,
        reply_markup=ui.reply_markup,
    )

    # Also refresh partner's prompt message (best effort) so the send button disappears for this pair.
    partner_tg_id = user_b.tg_id if user_a.tg_id == tg_id else user_a.tg_id
    await refresh_aggregated_wish_prompt(
        session=session,
        telegram_messenger=telegram_messenger,
        tg_id=partner_tg_id,
        pic_type="morning",
        day=today,
    )

    # Notify initiator that the wish was delivered
    pairs_repo = PairsRepository(session)
    partner_user = user_b if user_a.id == user_id else user_a
    partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user_id)
    partner_text = format_partner_text(
        partner_user.username if partner_user else None,
        partner_nickname,
    )
    await telegram_messenger.send_message(
        chat_id=tg_id,
        text=get_message("CALLBACK_WISH_DELIVERED", partner_text=partner_text),
    )

    # Schedule reminder tasks
    partner_tg_id = user_b.tg_id if user_a.tg_id == tg_id else user_a.tg_id
    recipient_user = user_b if user_a.id == user_id else user_a

    await schedule_reminder_tasks(
        pair_id=pair_id,
        initiator_tg_id=tg_id,
        recipient_tg_id=partner_tg_id,
        recipient_user_id=recipient_user.id,
        pic_type="morning",
        settings=settings,
    )

