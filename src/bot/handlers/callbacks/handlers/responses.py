"""Response handlers (tap_morning, tap_evening)."""

from datetime import date

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.messages import get_message
from src.core.logger import get_logger
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.telegram.messenger import TelegramMessenger
from src.bot.handlers.callbacks.validators import parse_callback_data_with_day
from src.bot.handlers.callbacks.use_cases.respond_to_wish import respond_to_wish
from src.bot.handlers.start.services.pair_service import format_partner_text

logger = get_logger(__name__)

router = Router(name="responses")


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


async def _build_partner_text_for_response(
    session: AsyncSession,
    pair_id: int,
    responder_tg_id: int,
    initiator_tg_id: int,
) -> str:
    pairs_repo = PairsRepository(session)
    users_repo = UsersRepository(session)
    pair = await pairs_repo.get_by_id(pair_id)
    if not pair:
        return get_message("START_PARTNER_FALLBACK")

    responder = await users_repo.get_by_tg_id(responder_tg_id)
    initiator = await users_repo.get_by_tg_id(initiator_tg_id)
    responder_id = responder.id if responder else None
    partner_nickname = (
        pairs_repo.get_my_nickname_for_partner(pair, responder_id)
        if responder_id
        else None
    )
    return format_partner_text(
        initiator.username if initiator else None,
        partner_nickname,
    )

@router.callback_query(F.data.startswith("tap_morning_"))
async def handle_tap_morning(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle morning tap (response)."""
    tg_id = callback.from_user.id
    
    # NOTE: We don't check is_message_active here because "Отправить в ответ" button
    # should work all day regardless of other messages (e.g., subscription reminders).
    # The respond_to_wish function already has proper checks for already_responded, etc.

    # Parse callback data: tap_morning_{pair_id}_{initiator_tg_id}|{day_iso}
    parsed = parse_callback_data_with_day(callback.data, prefix="tap_morning_")
    if not parsed:
        await _safe_callback_answer(callback, get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    pair_id, initiator_tg_id, day_iso = parsed
    
    # Determine which day to check
    check_day = date.fromisoformat(day_iso) if day_iso else date.today()
    
    logger.info(
        "Processing tap_morning callback",
        pair_id=pair_id,
        initiator_tg_id=initiator_tg_id,
        tg_id=tg_id,
        check_day=str(check_day),
        callback_data=callback.data,
    )
    
    # Respond to wish
    success, error_key = await respond_to_wish(
        session=session,
        pair_id=pair_id,
        check_day=check_day,
        tg_id=tg_id,
        initiator_tg_id=initiator_tg_id,
        pic_type="morning",
        telegram_messenger=telegram_messenger,
    )
    
    if not success:
        await _safe_callback_answer(
            callback, get_message(error_key or "CALLBACK_ERROR_GENERIC"), show_alert=True
        )
        return
    
    # Remove button from the message
    await telegram_messenger.remove_reply_markup(
        chat_id=tg_id,
        message_id=callback.message.message_id,
    )
    
    partner_text = await _build_partner_text_for_response(
        session=session,
        pair_id=pair_id,
        responder_tg_id=tg_id,
        initiator_tg_id=initiator_tg_id,
    )

    # Send confirmation message
    await telegram_messenger.send_message(
        chat_id=tg_id,
        text=get_message("CALLBACK_WISH_RESPONDED"),
    )
    await telegram_messenger.send_message(
        chat_id=tg_id,
        text=get_message("CALLBACK_RESPONSE_DELIVERED", partner_text=partner_text),
    )

    await _safe_callback_answer(callback, get_message("CALLBACK_RESPONSE_SENT"))


@router.callback_query(F.data.startswith("tap_evening_"))
async def handle_tap_evening(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle evening tap (response)."""
    tg_id = callback.from_user.id
    
    # NOTE: We don't check is_message_active here because "Отправить в ответ" button
    # should work all day regardless of other messages (e.g., subscription reminders).
    # The respond_to_wish function already has proper checks for already_responded, etc.

    # Parse callback data: tap_evening_{pair_id}_{initiator_tg_id}|{day_iso}
    parsed = parse_callback_data_with_day(callback.data, prefix="tap_evening_")
    if not parsed:
        await _safe_callback_answer(callback, get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return
    
    pair_id, initiator_tg_id, day_iso = parsed
    
    # Determine which day to check
    check_day = date.fromisoformat(day_iso) if day_iso else date.today()
    
    logger.info(
        "Processing tap_evening callback",
        pair_id=pair_id,
        initiator_tg_id=initiator_tg_id,
        tg_id=tg_id,
        check_day=str(check_day),
        callback_data=callback.data,
    )
    
    # Respond to wish
    success, error_key = await respond_to_wish(
        session=session,
        pair_id=pair_id,
        check_day=check_day,
        tg_id=tg_id,
        initiator_tg_id=initiator_tg_id,
        pic_type="evening",
        telegram_messenger=telegram_messenger,
    )
    
    if not success:
        await _safe_callback_answer(
            callback, get_message(error_key or "CALLBACK_ERROR_GENERIC"), show_alert=True
        )
        return
    
    # Remove button from the message
    await telegram_messenger.remove_reply_markup(
        chat_id=tg_id,
        message_id=callback.message.message_id,
    )
    
    partner_text = await _build_partner_text_for_response(
        session=session,
        pair_id=pair_id,
        responder_tg_id=tg_id,
        initiator_tg_id=initiator_tg_id,
    )

    # Send confirmation message
    await telegram_messenger.send_message(
        chat_id=tg_id,
        text=get_message("CALLBACK_WISH_RESPONDED"),
    )
    await telegram_messenger.send_message(
        chat_id=tg_id,
        text=get_message("CALLBACK_RESPONSE_DELIVERED", partner_text=partner_text),
    )

    await _safe_callback_answer(callback, get_message("CALLBACK_RESPONSE_SENT"))

