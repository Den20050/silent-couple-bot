"""Admin menu handlers."""

from datetime import date, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.constants import PairStatus, SUBSCRIPTION_PLANS
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.models import Pair, Subscription, User
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.pair_demo import PairDemoRepository
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.db.repositories.users import UsersRepository
from src.services.telegram.messenger import TelegramMessenger
from src.services.messaging.ui.menu_ui import MenuUIService
from src.services.messaging.ui.admin_ui import AdminUIService
from src.bot.handlers.menu.states import AdminStates

from src.bot.handlers.admin.use_cases.stats import (
    DEFAULT_ADMIN_STATS_PERIOD_DAYS,
    DEFAULT_ADMIN_STATS_TAB,
    get_admin_statistics,
)

logger = get_logger(__name__)

router = Router(name="menu_admin")


def _parse_stats_period(callback_data: str) -> int | None:
    """Parse admin_stats_period:{days|all} callback (legacy)."""
    raw = callback_data.removeprefix("admin_stats_period:")
    if raw == "all":
        return None
    return int(raw)


def _parse_stats_view(callback_data: str) -> tuple[str, int | None]:
    """Parse admin_stats_view:{tab}:{period} callback."""
    parts = callback_data.removeprefix("admin_stats_view:").split(":")
    tab = parts[0] if parts and parts[0] in ("users", "payments") else DEFAULT_ADMIN_STATS_TAB
    period_raw = parts[1] if len(parts) > 1 else str(DEFAULT_ADMIN_STATS_PERIOD_DAYS)
    period_days = None if period_raw == "all" else int(period_raw)
    return tab, period_days


async def _show_admin_stats(
    message_or_callback: Message | CallbackQuery,
    session: AsyncSession,
    menu_ui: MenuUIService,
    period_days: int | None = DEFAULT_ADMIN_STATS_PERIOD_DAYS,
    stats_tab: str = DEFAULT_ADMIN_STATS_TAB,
) -> None:
    admin_ui = AdminUIService()
    stats = await get_admin_statistics(
        session,
        period_days=period_days,
        stats_tab=stats_tab,
    )
    stats_message = admin_ui.format_statistics_message(stats)
    keyboard = admin_ui.build_stats_keyboard(
        stats.get("stats_tab", stats_tab),
        stats.get("period_days", period_days),
    )

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(
            stats_message,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await message_or_callback.answer()
        logger.info(
            "Admin statistics requested",
            admin_tg_id=message_or_callback.from_user.id,
            **stats,
        )
    else:
        await message_or_callback.answer(
            stats_message,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        logger.info(
            "Admin statistics requested",
            admin_tg_id=message_or_callback.from_user.id,
            **stats,
        )


@router.callback_query(lambda c: c.data == "menu_admin_enter")
async def handle_menu_admin_enter(
    callback: CallbackQuery,
    session: AsyncSession,  # noqa: ARG001
    settings: Settings,
    menu_ui: MenuUIService,
) -> None:
    """Handle admin menu button click - show admin menu."""
    try:
        tg_id = callback.from_user.id
        
        # Check if user is admin
        if not menu_ui._is_admin(tg_id):
            await callback.answer(get_message("MENU_ADMIN_ONLY"), show_alert=True)
            return
        
        text = "👑 <b>Админ-меню</b>\n\nВыберите действие:"
        
        await callback.message.edit_text(
            text,
            reply_markup=menu_ui.build_admin_menu_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
    except Exception as e:
        logger.error("Error in handle_menu_admin_enter", error=str(e), exc_info=True)
        await callback.answer(
            get_message("MENU_ERROR"),
            show_alert=True,
        )


@router.callback_query(lambda c: c.data == "admin_stats_callback")
async def handle_admin_stats_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    menu_ui: MenuUIService,
) -> None:
    """Handle admin stats callback from menu."""
    if not menu_ui._is_admin(callback.from_user.id):
        await callback.answer(get_message("MENU_ADMIN_ONLY"), show_alert=True)
        return

    try:
        await _show_admin_stats(callback, session, menu_ui)
    except Exception as e:
        logger.error("Error getting admin statistics", error=str(e), exc_info=True)
        await callback.answer(get_message("ADMIN_STATS_ERROR"), show_alert=True)


@router.callback_query(F.data.startswith("admin_stats_view:"))
async def handle_admin_stats_view_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    menu_ui: MenuUIService,
) -> None:
    """Handle admin stats tab/period selection."""
    if not menu_ui._is_admin(callback.from_user.id):
        await callback.answer(get_message("MENU_ADMIN_ONLY"), show_alert=True)
        return

    try:
        stats_tab, period_days = _parse_stats_view(callback.data)
        await _show_admin_stats(
            callback,
            session,
            menu_ui,
            period_days=period_days,
            stats_tab=stats_tab,
        )
    except Exception as e:
        logger.error("Error getting admin statistics", error=str(e), exc_info=True)
        await callback.answer(get_message("ADMIN_STATS_ERROR"), show_alert=True)


@router.callback_query(F.data.startswith("admin_stats_period:"))
async def handle_admin_stats_period_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    menu_ui: MenuUIService,
) -> None:
    """Handle legacy admin stats period selection."""
    if not menu_ui._is_admin(callback.from_user.id):
        await callback.answer(get_message("MENU_ADMIN_ONLY"), show_alert=True)
        return

    try:
        period_days = _parse_stats_period(callback.data)
        await _show_admin_stats(callback, session, menu_ui, period_days=period_days)
    except Exception as e:
        logger.error("Error getting admin statistics", error=str(e), exc_info=True)
        await callback.answer(get_message("ADMIN_STATS_ERROR"), show_alert=True)


@router.callback_query(lambda c: c.data == "admin_reset_demo_callback")
async def handle_admin_reset_demo_callback(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    menu_ui: MenuUIService,
) -> None:
    """Handle admin reset demo callback from menu."""
    if not menu_ui._is_admin(callback.from_user.id):
        await callback.answer(get_message("MENU_ADMIN_ONLY"), show_alert=True)
        return
    
    try:
        text = get_message("ADMIN_RESET_DEMO_PROMPT")
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_message("MENU_BACK_BUTTON"),
                        callback_data="menu_back",
                    ),
                ],
            ]
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(AdminStates.waiting_tg_id)
        await state.update_data(action="reset_demo")
        await callback.answer()
    except Exception as e:
        logger.error("Error in handle_admin_reset_demo_callback", error=str(e), exc_info=True)
        await callback.answer(get_message("MENU_ERROR"), show_alert=True)


@router.callback_query(lambda c: c.data == "admin_gift_callback")
async def handle_admin_gift_callback(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    menu_ui: MenuUIService,
) -> None:
    """Handle admin gift callback from menu."""
    if not menu_ui._is_admin(callback.from_user.id):
        await callback.answer(get_message("MENU_ADMIN_ONLY"), show_alert=True)
        return
    
    try:
        text = (
            "🎁 <b>Подарить подписку</b>\n\n"
            "Отправьте Telegram ID пользователя для подарка подписки.\n\n"
            "Если пользователь состоит в паре, подписка будет подарена обоим пользователям пары.\n\n"
            "Для отмены отправьте /cancel"
        )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_message("MENU_BACK_BUTTON"),
                        callback_data="menu_back",
                    ),
                ],
            ]
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(AdminStates.waiting_tg_id)
        await state.update_data(action="gift_subscription")
        await callback.answer()
    except Exception as e:
        logger.error("Error in handle_admin_gift_callback", error=str(e), exc_info=True)
        await callback.answer(get_message("MENU_ERROR"), show_alert=True)


@router.callback_query(lambda c: c.data == "admin_broadcast_callback")
async def handle_admin_broadcast_callback(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    menu_ui: MenuUIService,
) -> None:
    """Handle admin broadcast callback from menu."""
    if not menu_ui._is_admin(callback.from_user.id):
        await callback.answer(get_message("MENU_ADMIN_ONLY"), show_alert=True)
        return
    
    try:
        text = get_message("ADMIN_BROADCAST_PROMPT")
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_message("MENU_BACK_BUTTON"),
                        callback_data="menu_back",
                    ),
                ],
            ]
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(AdminStates.waiting_broadcast_message)
        await callback.answer()
    except Exception as e:
        logger.error("Error in handle_admin_broadcast_callback", error=str(e), exc_info=True)
        await callback.answer(get_message("MENU_ERROR"), show_alert=True)


@router.message(Command("admin_stats"))
async def cmd_admin_stats(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    menu_ui: MenuUIService,
) -> None:
    """Handle /admin_stats command."""
    if not menu_ui._is_admin(message.from_user.id):
        await message.answer(get_message("MENU_ADMIN_ONLY"))
        return
    
    try:
        await _show_admin_stats(message, session, menu_ui)
    except Exception as e:
        logger.error("Error getting admin statistics", error=str(e), exc_info=True)
        await message.answer(get_message("ADMIN_STATS_ERROR"))


@router.message(Command("admin_reset_demo"))
async def cmd_admin_reset_demo(
    message: Message,
    state: FSMContext,
    settings: Settings,
    menu_ui: MenuUIService,
) -> None:
    """Handle /admin_reset_demo command - ask for tg_id."""
    if not menu_ui._is_admin(message.from_user.id):
        await message.answer(get_message("MENU_ADMIN_ONLY"))
        return
    
    try:
        text = get_message("ADMIN_RESET_DEMO_PROMPT")
        
        await message.answer(text, parse_mode="HTML")
        await state.set_state(AdminStates.waiting_tg_id)
        await state.update_data(action="reset_demo")
    except Exception as e:
        logger.error("Error in cmd_admin_reset_demo", error=str(e), exc_info=True)
        await message.answer(get_message("MENU_ERROR"))


@router.message(Command("admin_gift"))
async def cmd_admin_gift(
    message: Message,
    state: FSMContext,
    settings: Settings,
    menu_ui: MenuUIService,
) -> None:
    """Handle /admin_gift command - ask for tg_id."""
    if not menu_ui._is_admin(message.from_user.id):
        await message.answer(get_message("MENU_ADMIN_ONLY"))
        return
    
    try:
        text = (
            "🎁 <b>Подарить подписку</b>\n\n"
            "Отправьте Telegram ID пользователя для подарка подписки.\n\n"
            "Если пользователь состоит в паре, подписка будет подарена обоим пользователям пары.\n\n"
            "Для отмены отправьте /cancel"
        )
        
        await message.answer(text, parse_mode="HTML")
        await state.set_state(AdminStates.waiting_tg_id)
        await state.update_data(action="gift_subscription")
    except Exception as e:
        logger.error("Error in cmd_admin_gift", error=str(e), exc_info=True)
        await message.answer(get_message("MENU_ERROR"))


@router.message(Command("admin_broadcast"))
async def cmd_admin_broadcast(
    message: Message,
    state: FSMContext,
    settings: Settings,
    menu_ui: MenuUIService,
) -> None:
    """Handle /admin_broadcast command - ask for message."""
    if not menu_ui._is_admin(message.from_user.id):
        await message.answer(get_message("MENU_ADMIN_ONLY"))
        return
    
    try:
        text = get_message("ADMIN_BROADCAST_PROMPT")
        
        await message.answer(text, parse_mode="HTML")
        await state.set_state(AdminStates.waiting_broadcast_message)
    except Exception as e:
        logger.error("Error in cmd_admin_broadcast", error=str(e), exc_info=True)
        await message.answer(get_message("MENU_ERROR"))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Handle /cancel command - cancel current operation."""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer(get_message("MENU_OPERATION_CANCELLED"))
    else:
        await message.answer("Нет активных операций для отмены.")

