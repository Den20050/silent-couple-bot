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

logger = get_logger(__name__)

router = Router(name="menu_admin")


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
    settings: Settings,
) -> None:
    """Handle admin stats callback from menu."""
    if not menu_ui._is_admin(callback.from_user.id):
        await callback.answer(get_message("MENU_ADMIN_ONLY"), show_alert=True)
        return
    
    try:
        from src.bot.handlers.admin.use_cases.stats import get_admin_statistics

        stats = await get_admin_statistics(session)
        stats_message = AdminUIService().format_statistics_message(stats)

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

        await callback.message.edit_text(stats_message, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
        
        logger.info(
            "Admin statistics requested",
            admin_tg_id=callback.from_user.id,
            **stats,
        )
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
        from src.bot.handlers.admin.use_cases.stats import get_admin_statistics

        stats = await get_admin_statistics(session)
        stats_message = AdminUIService().format_statistics_message(stats)

        await message.answer(stats_message, parse_mode="HTML")
        
        logger.info(
            "Admin statistics requested",
            admin_tg_id=message.from_user.id,
            **stats,
        )
    except Exception as e:
        logger.error("Error getting admin statistics", error=str(e), exc_info=True)
        await message.answer(get_message("ADMIN_STATS_ERROR"))


@router.message(Command("admin_subscription_status"))
async def cmd_admin_subscription_status(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    menu_ui: MenuUIService,
) -> None:
    """Handle /admin_subscription_status command."""
    if not menu_ui._is_admin(message.from_user.id):
        await message.answer(get_message("MENU_ADMIN_ONLY"))
        return

    try:
        args = message.text.split()[1:] if message.text else []
        if not args:
            await message.answer(get_message("ADMIN_SUBSCRIPTION_STATUS_USAGE"))
            return

        try:
            tg_id = int(args[0])
        except ValueError:
            await message.answer(get_message("ADMIN_INVALID_TG_ID_FORMAT"))
            return

        users_repo = UsersRepository(session)
        pairs_repo = PairsRepository(session)
        subs_repo = SubscriptionsRepository(session)

        user = await users_repo.get_by_tg_id(tg_id)
        if not user:
            await message.answer(get_message("MENU_USER_NOT_FOUND_FORMAT", tg_id=tg_id))
            return

        pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
        if not pairs:
            await message.answer(get_message("ADMIN_SUBSCRIPTION_STATUS_NO_PAIRS", tg_id=tg_id))
            return

        lines = [f"🧾 <b>Статус подписки</b> (tg_id {tg_id})"]
        for pair in pairs:
            partner_id = pair.uid_b if pair.uid_a == user.id else pair.uid_a
            partner = await users_repo.get_by_id(partner_id)
            partner_tg_id = partner.tg_id if partner else "—"

            subscription = await subs_repo.get_by_pair_id(pair.id)
            subscription_status = subscription.status if subscription else "none"
            period_end = "—"
            if subscription:
                if subscription.is_lifetime:
                    period_end = "Навсегда"
                elif subscription.period_end:
                    period_end = subscription.period_end.strftime("%d.%m.%Y")

            lines.append(
                "\n".join(
                    [
                        f"\n<b>Пара {pair.id}</b> (партнёр: {partner_tg_id})",
                        f"• Статус пары: {pair.status}",
                        f"• Статус подписки: {subscription_status}",
                        f"• Период до: {period_end}",
                        f"• Payment ID: {subscription.yoo_id if subscription else '—'}",
                        (
                            f"• Last past due: {subscription.last_past_due_notification_date}"
                            if subscription and subscription.last_past_due_notification_date
                            else "• Last past due: —"
                        ),
                    ]
                )
            )

        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        logger.error(
            "Error in cmd_admin_subscription_status",
            error=str(e),
            exc_info=True,
        )
        await message.answer(get_message("MENU_ERROR"))


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

