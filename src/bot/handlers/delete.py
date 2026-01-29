"""Delete command handler (GDPR) and pair unlink flow."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.models import LifetimePairHistory
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.db.repositories.users import UsersRepository
from aiogram.fsm.context import FSMContext

from src.services.telegram.messenger import TelegramMessenger
from src.bot.handlers.start.services.pair_service import format_partner_text

logger = get_logger(__name__)

router = Router(name="delete")


async def _get_partner_info(
    session: AsyncSession,
    pair,
    user,
    pairs_repo: PairsRepository,
    users_repo: UsersRepository,
) -> tuple[object | None, str]:
    partner_id = pair.uid_b if pair.uid_a == user.id else pair.uid_a
    partner = await users_repo.get_by_id(partner_id)
    partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user.id)
    partner_text = format_partner_text(
        partner.username if partner else None,
        partner_nickname,
    )
    return partner, partner_text


async def _ensure_lifetime_history(
    session: AsyncSession,
    pair,
    user_id: int,
    subs_repo: SubscriptionsRepository,
) -> None:
    subscription = await subs_repo.get_by_pair_id(pair.id)
    if not subscription or not subscription.is_lifetime:
        return

    partner_id = pair.uid_b if pair.uid_a == user_id else pair.uid_a
    uid_a, uid_b = (
        (user_id, partner_id) if user_id < partner_id else (partner_id, user_id)
    )
    existing_history = await session.execute(
        select(LifetimePairHistory).where(
            LifetimePairHistory.uid_a == uid_a,
            LifetimePairHistory.uid_b == uid_b,
        )
    )
    if existing_history.scalar_one_or_none():
        return

    session.add(LifetimePairHistory(uid_a=uid_a, uid_b=uid_b))
    await session.flush()

    logger.info(
        "Lifetime pair broken - added to history",
        user_id=user_id,
        partner_id=partner_id,
        pair_id=pair.id,
    )


def _get_pair_status_label(status: str | None) -> str:
    if status == PairStatus.TRIAL.value:
        return "демо"
    if status == PairStatus.ACTIVE.value:
        return "активна"
    if status == PairStatus.PAST_DUE.value:
        return "просрочена"
    if status == PairStatus.CANCELLED.value:
        return "отменена"
    return "неизвестно"


def _build_pairs_keyboard(pairs, partner_texts: dict[int, str]) -> InlineKeyboardMarkup:
    keyboard = []
    for pair in pairs:
        base_text = partner_texts.get(pair.id, f"Пара #{pair.id}")
        status_label = _get_pair_status_label(pair.status)
        button_text = f"{base_text} ({status_label})"
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"delete_select_pair_{pair.id}",
            )
        ])
    keyboard.append([
        InlineKeyboardButton(
            text=get_message("DELETE_CANCEL_BUTTON"),
            callback_data="delete_cancel",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _build_confirm_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("DELETE_CONFIRM_BUTTON"),
                    callback_data=callback_data,
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_message("DELETE_CANCEL_BUTTON"),
                    callback_data="delete_cancel",
                )
            ],
        ]
    )


@router.message(Command("delete"))
async def cmd_delete(
    message: Message,
    session: AsyncSession,
) -> None:
    """Handle /delete command with confirmation flow."""
    await _show_delete_flow(
        tg_id=message.from_user.id,
        session=session,
        message=message,
    )


@router.callback_query(F.data == "menu_delete")
async def handle_menu_delete(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Handle delete menu item."""
    await state.clear()
    await _show_delete_flow(
        tg_id=callback.from_user.id,
        session=session,
        callback=callback,
    )


async def _show_delete_flow(
    *,
    tg_id: int,
    session: AsyncSession,
    message: Message | None = None,
    callback: CallbackQuery | None = None,
) -> None:
    users_repo = UsersRepository(session)
    pairs_repo = PairsRepository(session)

    user = await users_repo.get_by_tg_id(tg_id)
    if not user:
        if message:
            await message.answer(get_message("DELETE_DATA_NOT_FOUND"))
        elif callback:
            await callback.answer(get_message("DELETE_DATA_NOT_FOUND"), show_alert=True)
        return

    pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    if not pairs:
        text = get_message("DELETE_CONFIRM_NO_PAIRS")
        keyboard = _build_confirm_keyboard("delete_confirm_account")
        if message:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()
        return

    if len(pairs) == 1:
        pair = pairs[0]
        _partner, partner_text = await _get_partner_info(
            session=session,
            pair=pair,
            user=user,
            pairs_repo=pairs_repo,
            users_repo=users_repo,
        )
        text = get_message("DELETE_CONFIRM_SINGLE", partner_text=partner_text)
        keyboard = _build_confirm_keyboard(f"delete_confirm_pair_{pair.id}")
        if message:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer()
        return

    partner_texts: dict[int, str] = {}
    for pair in pairs:
        _partner, partner_text = await _get_partner_info(
            session=session,
            pair=pair,
            user=user,
            pairs_repo=pairs_repo,
            users_repo=users_repo,
        )
        partner_texts[pair.id] = partner_text

    text = get_message("DELETE_SELECT_PAIR_TITLE")
    keyboard = _build_pairs_keyboard(pairs, partner_texts)
    if message:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()


@router.callback_query(F.data.startswith("delete_select_pair_"))
async def handle_delete_select_pair(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Handle selecting a pair to delete."""
    try:
        pair_id = int(callback.data.replace("delete_select_pair_", ""))
    except ValueError:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    users_repo = UsersRepository(session)
    pairs_repo = PairsRepository(session)
    user = await users_repo.get_by_tg_id(callback.from_user.id)
    pair = await pairs_repo.get_by_id(pair_id)
    if not user or not pair or user.id not in (pair.uid_a, pair.uid_b):
        await callback.answer(get_message("CALLBACK_ACCESS_DENIED"), show_alert=True)
        return

    _partner, partner_text = await _get_partner_info(
        session=session,
        pair=pair,
        user=user,
        pairs_repo=pairs_repo,
        users_repo=users_repo,
    )
    text = get_message("DELETE_CONFIRM_MULTI", partner_text=partner_text)
    keyboard = _build_confirm_keyboard(f"delete_confirm_pair_{pair.id}")
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "delete_cancel")
async def handle_delete_cancel(callback: CallbackQuery) -> None:
    """Cancel deletion flow."""
    try:
        await callback.message.delete()
        await callback.answer()
    except Exception:
        await callback.answer()


@router.callback_query(F.data == "delete_confirm_account")
async def handle_delete_confirm_account(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Confirm account deletion when user has no pairs."""
    users_repo = UsersRepository(session)
    user = await users_repo.get_by_tg_id(callback.from_user.id)
    if not user:
        await callback.answer(get_message("DELETE_DATA_NOT_FOUND"), show_alert=True)
        return

    await session.delete(user)
    await session.commit()
    await callback.message.edit_text(
        get_message("DELETE_ACCOUNT_REMOVED"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_confirm_pair_"))
async def handle_delete_confirm_pair(
    callback: CallbackQuery,
    session: AsyncSession,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Confirm pair deletion (and account deletion if it was the last pair)."""
    try:
        pair_id = int(callback.data.replace("delete_confirm_pair_", ""))
    except ValueError:
        await callback.answer(get_message("CALLBACK_ERROR_GENERIC"), show_alert=True)
        return

    users_repo = UsersRepository(session)
    pairs_repo = PairsRepository(session)
    subs_repo = SubscriptionsRepository(session)

    user = await users_repo.get_by_tg_id(callback.from_user.id)
    pair = await pairs_repo.get_by_id(pair_id)
    if not user or not pair or user.id not in (pair.uid_a, pair.uid_b):
        await callback.answer(get_message("CALLBACK_ACCESS_DENIED"), show_alert=True)
        return

    partner, partner_text = await _get_partner_info(
        session=session,
        pair=pair,
        user=user,
        pairs_repo=pairs_repo,
        users_repo=users_repo,
    )

    pre_pairs = await pairs_repo.get_all_by_user_tg_id(callback.from_user.id)
    pre_pairs_count = len(pre_pairs)

    await _ensure_lifetime_history(
        session=session,
        pair=pair,
        user_id=user.id,
        subs_repo=subs_repo,
    )

    partner_tg_id = partner.tg_id if partner else None
    partner_nickname_for_user = (
        pairs_repo.get_my_nickname_for_partner(pair, partner.id)
        if partner
        else None
    )
    partner_view_text = format_partner_text(
        user.username if user else None,
        partner_nickname_for_user,
    )

    await session.delete(pair)
    await session.flush()

    remaining_pairs = await pairs_repo.get_all_by_user_tg_id(callback.from_user.id)
    delete_account = len(remaining_pairs) == 0

    if delete_account:
        await session.delete(user)

    await session.commit()

    if delete_account and pre_pairs_count == 1:
        await callback.message.edit_text(
            get_message("DELETE_ACCOUNT_REMOVED"),
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(
            get_message("DELETE_LINK_REMOVED", partner_text=partner_text),
            parse_mode="HTML",
        )
        if delete_account:
            await telegram_messenger.send_message(
                chat_id=callback.from_user.id,
                text=get_message("DELETE_ACCOUNT_REMOVED"),
                parse_mode="HTML",
            )

    if partner_tg_id:
        await telegram_messenger.send_message(
            chat_id=partner_tg_id,
            text=get_message("DELETE_PARTNER_NOTICE", partner_text=partner_view_text),
            parse_mode="HTML",
        )

    await callback.answer()

