"""Evening request handlers."""

from datetime import date

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.messages import get_message
from src.core.logger import get_logger
from src.core.di.container import Container
from src.services.telegram.messenger import TelegramMessenger
from src.bot.handlers.callbacks.validators import parse_callback_data, parse_callback_data_with_day
from src.services.messaging.process_wish_request import process_wish_request
from src.services.messaging.ui.wish_request_ui import WishRequestUIService
from src.services.messaging.active_action_message import is_message_active, ActionKind

logger = get_logger(__name__)

router = Router(name="evening_requests")


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


@router.callback_query(F.data.startswith("request_evening_all_"))
async def handle_request_evening_all_legacy(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Legacy handler: 'send to all' is deprecated; convert prompt to per-partner UI."""
    parsed = parse_callback_data(
        callback.data, expected_parts=4, prefix="request_evening_all_"
    )
    if not parsed:
        await _safe_callback_answer(callback, get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    (user_id,) = parsed
    tg_id = callback.from_user.id

    from src.db.repositories.users import UsersRepository

    users_repo = UsersRepository(session)
    user = await users_repo.get_by_id(user_id)
    if not user or user.tg_id != tg_id:
        await _safe_callback_answer(callback, get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    today = date.today()
    ui_builder = WishRequestUIService(session)
    ui = await ui_builder.build_for_user(user_tg_id=tg_id, pic_type="evening", day=today)

    await telegram_messenger.edit_message(
        chat_id=tg_id,
        message_id=callback.message.message_id,
        text=ui.text,
        reply_markup=ui.reply_markup,
    )
    await _safe_callback_answer(callback, "ℹ️ Выберите партнёра")


@router.callback_query(F.data.startswith("request_evening_"))
async def handle_request_evening(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
    settings: Settings,
    container: Container,
) -> None:
    """Handle legacy evening request callback buttons (pre-WebApp prompts)."""
    tg_id = callback.from_user.id
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

    parsed = parse_callback_data_with_day(callback.data, prefix="request_evening_")
    if not parsed:
        return

    pair_id, user_id, day_iso = parsed
    today = date.fromisoformat(day_iso) if day_iso else date.today()

    logger.info(
        "Processing legacy request_evening callback",
        pair_id=pair_id,
        user_id=user_id,
        tg_id=tg_id,
        callback_data=callback.data,
    )

    await process_wish_request(
        session=session,
        telegram_messenger=telegram_messenger,
        settings=settings,
        redis=container.redis,
        tg_id=tg_id,
        pair_id=pair_id,
        user_id=user_id,
        pic_type="evening",
        day=today,
        prompt_message_id=callback.message.message_id if callback.message else None,
    )
