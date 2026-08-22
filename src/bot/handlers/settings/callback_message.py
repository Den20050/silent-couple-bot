"""Helpers for editing callback messages safely."""

from __future__ import annotations

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from src.core.logger import get_logger

logger = get_logger(__name__)


def coerce_inline_keyboard(
    reply_markup: InlineKeyboardMarkup | dict | None,
) -> InlineKeyboardMarkup | None:
    if reply_markup is None:
        return None
    if isinstance(reply_markup, InlineKeyboardMarkup):
        return reply_markup
    return InlineKeyboardMarkup.model_validate(reply_markup)


async def safe_edit_callback_message(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | dict | None = None,
    parse_mode: ParseMode = ParseMode.HTML,
) -> None:
    """Answer callback first, then edit message; fall back to a new message."""
    markup = coerce_inline_keyboard(reply_markup)
    await callback.answer()
    try:
        await callback.message.edit_text(
            text,
            reply_markup=markup,
            parse_mode=parse_mode,
        )
    except TelegramBadRequest as exc:
        error_text = str(exc).lower()
        if "message is not modified" in error_text:
            return
        logger.warning(
            "edit_text failed in settings callback, sending new message",
            callback_data=callback.data,
            error=str(exc),
        )
        await callback.message.answer(
            text,
            reply_markup=markup,
            parse_mode=parse_mode,
        )
